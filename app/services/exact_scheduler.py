import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.scheduled_post import ScheduledPost
from app.services.publishing import process_due_posts


logger = logging.getLogger(__name__)

_scheduler_loop: asyncio.AbstractEventLoop | None = None
_wake_event: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


def notify_schedule_changed() -> None:
    """Wake the scheduler after a schedule is created, edited, or cancelled.

    FastAPI sync routes run in a thread pool, so wake the asyncio worker through
    the event loop's thread-safe callback API.
    """
    loop = _scheduler_loop
    event = _wake_event
    if loop is None or event is None or loop.is_closed():
        return

    try:
        loop.call_soon_threadsafe(event.set)
    except RuntimeError:
        # The application can be shutting down while a request is completing.
        return


def scheduler_status() -> dict:
    task = _worker_task
    return {
        "running": bool(task and not task.done()),
        "mode": "exact-time",
    }


def _next_scheduled_time() -> datetime | None:
    db = SessionLocal()
    try:
        return (
            db.query(ScheduledPost.schedule_time)
            .filter(ScheduledPost.publish_state == "scheduled")
            .order_by(ScheduledPost.schedule_time.asc())
            .limit(1)
            .scalar()
        )
    finally:
        db.close()


def _publish_due() -> dict:
    db = SessionLocal()
    try:
        return process_due_posts(db)
    finally:
        db.close()


async def _scheduler_worker() -> None:
    """Sleep until the next DB timestamp, then publish due posts immediately.

    Unlike a cron poller, this worker does not round schedules to five-minute
    intervals. A newly created/rescheduled post wakes the worker so it can
    recalculate the nearest exact timestamp.
    """
    event = _wake_event
    if event is None:
        return

    while True:
        try:
            # Clear before reading the database. If a request commits a new
            # schedule after this point, notify_schedule_changed() sets the
            # event and the wait below returns immediately to recalculate.
            event.clear()
            next_time = await asyncio.to_thread(_next_scheduled_time)

            if next_time is None:
                await event.wait()
                continue

            if next_time.tzinfo is None:
                next_time = next_time.replace(tzinfo=timezone.utc)

            delay = max(
                0.0,
                (next_time.astimezone(timezone.utc) - datetime.now(timezone.utc)).total_seconds(),
            )

            if delay > 0:
                try:
                    await asyncio.wait_for(event.wait(), timeout=delay)
                    # A create/reschedule/cancel happened before the old target.
                    # Re-read the database instead of waiting for the stale time.
                    continue
                except asyncio.TimeoutError:
                    pass

            result = await asyncio.to_thread(_publish_due)
            if result.get("processed"):
                logger.info(
                    "Exact scheduler processed %s post(s): %s published, %s failed",
                    result.get("processed", 0),
                    result.get("published", 0),
                    result.get("failed", 0),
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Exact scheduled publishing worker failed; retrying")
            await asyncio.sleep(2)


async def start_exact_scheduler() -> None:
    global _scheduler_loop, _wake_event, _worker_task

    if _worker_task is not None and not _worker_task.done():
        return

    _scheduler_loop = asyncio.get_running_loop()
    _wake_event = asyncio.Event()
    _worker_task = asyncio.create_task(
        _scheduler_worker(),
        name="creatoros-exact-publishing-scheduler",
    )
    logger.info("CreatorOS exact scheduled publishing worker started")


async def stop_exact_scheduler() -> None:
    global _scheduler_loop, _wake_event, _worker_task

    task = _worker_task
    _worker_task = None

    if task is not None and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    _wake_event = None
    _scheduler_loop = None
    logger.info("CreatorOS exact scheduled publishing worker stopped")
