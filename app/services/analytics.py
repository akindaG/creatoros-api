from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.post import Post


def _latest_analytics(rows: list[Analytics]) -> list[Analytics]:
    latest: dict[object, Analytics] = {}
    for row in rows:
        latest[row.post_id] = row
    return list(latest.values())


def _latest_analytics_with_posts(rows: list[tuple[Analytics, Post]]) -> list[tuple[Analytics, Post]]:
    latest: dict[object, tuple[Analytics, Post]] = {}
    for analytics, post in rows:
        latest[post.id] = (analytics, post)
    return list(latest.values())


def dashboard_metrics(db: Session, user_id) -> dict:
    rows = (
        db.query(Analytics)
        .join(Post, Post.id == Analytics.post_id)
        .filter(Post.user_id == user_id)
        .order_by(Analytics.captured_at.asc(), Analytics.id.asc())
        .all()
    )
    posts_count = db.query(Post).filter(Post.user_id == user_id).count()
    if not rows:
        return {
            "followers": 0,
            "reach": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "engagement_rate": 0.0,
            "growth_rate": 0.0,
            "posts_count": posts_count,
        }

    # Analytics rows are point-in-time snapshots. Aggregate the latest snapshot
    # for each post so repeated captures do not double-count cumulative metrics.
    latest_rows = _latest_analytics(rows)
    reach = sum(row.reach for row in latest_rows)
    likes = sum(row.likes for row in latest_rows)
    comments = sum(row.comments for row in latest_rows)
    shares = sum(row.shares for row in latest_rows)
    engagement_rate = round(((likes + comments + shares) / reach * 100), 2) if reach else 0.0

    # Followers are account-level snapshots, so growth still uses the earliest
    # and most recent capture across the complete history.
    followers = rows[-1].followers
    first_followers = rows[0].followers
    growth_rate = round(((followers - first_followers) / first_followers * 100), 2) if first_followers else 0.0
    return {
        "followers": followers,
        "reach": reach,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "engagement_rate": engagement_rate,
        "growth_rate": growth_rate,
        "posts_count": posts_count,
    }


def analytics_overview(db: Session, user_id) -> dict:
    rows = (
        db.query(Analytics, Post)
        .join(Post, Post.id == Analytics.post_id)
        .filter(Post.user_id == user_id)
        .order_by(Analytics.captured_at.asc(), Analytics.id.asc())
        .all()
    )
    metrics = dashboard_metrics(db, user_id)

    # Keep historical snapshots for the trend chart.
    series = [
        {
            "captured_at": analytics.captured_at,
            "reach": analytics.reach,
            "engagements": analytics.likes + analytics.comments + analytics.shares,
            "engagement_rate": float(analytics.engagement_rate or 0),
        }
        for analytics, _ in rows[-30:]
    ]

    platform_reach = {"instagram": 0, "facebook": 0}
    top_posts = []
    for analytics, post in _latest_analytics_with_posts(rows):
        platform = (post.platform or "").lower()
        if platform in platform_reach:
            platform_reach[platform] += analytics.reach
        engagements = analytics.likes + analytics.comments + analytics.shares
        top_posts.append(
            {
                "post_id": post.id,
                "title": post.title,
                "platform": platform,
                "reach": analytics.reach,
                "engagements": engagements,
                "engagement_rate": round(engagements / analytics.reach * 100, 2) if analytics.reach else 0.0,
            }
        )

    top_posts.sort(key=lambda item: (item["engagement_rate"], item["engagements"]), reverse=True)

    return {
        "metrics": metrics,
        "series": series,
        "top_posts": top_posts[:5],
        "platform_reach": platform_reach,
    }


def best_posting_time(db: Session, user_id) -> dict:
    rows = (
        db.query(Analytics, Post)
        .join(Post, Post.id == Analytics.post_id)
        .filter(Post.user_id == user_id)
        .order_by(Analytics.captured_at.asc(), Analytics.id.asc())
        .all()
    )
    latest_rows = _latest_analytics_with_posts(rows)
    if not latest_rows:
        return {
            "best_day": None,
            "best_hour": None,
            "formatted_time": None,
            "confidence": 0.0,
            "sample_size": 0,
            "reason": "Not enough analytics data yet.",
        }

    buckets: dict[tuple[str, int], list[float]] = defaultdict(list)
    for analytics, post in latest_rows:
        dt = post.scheduled_time or post.created_at or analytics.captured_at
        score = analytics.likes + analytics.comments * 2 + analytics.shares * 3
        buckets[(dt.strftime("%A"), dt.hour)].append(float(score))
    averages = {key: sum(values) / len(values) for key, values in buckets.items()}
    best_key = max(averages, key=averages.get)
    best_score = averages[best_key]
    total = sum(averages.values()) or 1
    confidence = round(min(1.0, best_score / total + min(len(latest_rows), 20) / 40), 2)
    day, hour = best_key
    formatted = f"{(hour % 12) or 12}:00 {'AM' if hour < 12 else 'PM'}"
    return {
        "best_day": day,
        "best_hour": hour,
        "formatted_time": formatted,
        "confidence": confidence,
        "sample_size": len(latest_rows),
        "reason": f"{day} at {formatted} has the highest average weighted engagement in your stored history.",
    }
