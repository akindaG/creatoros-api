from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.analytics import Analytics
from app.models.post import Post


def dashboard_metrics(db: Session, user_id) -> dict:
    rows = (
        db.query(Analytics)
        .join(Post, Post.id == Analytics.post_id)
        .filter(Post.user_id == user_id)
        .order_by(Analytics.captured_at.asc())
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

    reach = sum(row.reach for row in rows)
    likes = sum(row.likes for row in rows)
    comments = sum(row.comments for row in rows)
    shares = sum(row.shares for row in rows)
    engagement_rate = round(((likes + comments + shares) / reach * 100), 2) if reach else 0.0
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
        .order_by(Analytics.captured_at.asc())
        .all()
    )
    metrics = dashboard_metrics(db, user_id)

    series = [
        {
            "captured_at": analytics.captured_at,
            "reach": analytics.reach,
            "engagements": analytics.likes + analytics.comments + analytics.shares,
            "engagement_rate": float(analytics.engagement_rate or 0),
        }
        for analytics, _ in rows[-30:]
    ]

    grouped: dict[object, dict] = {}
    platform_reach = {"instagram": 0, "facebook": 0}
    for analytics, post in rows:
        platform = (post.platform or "").lower()
        if platform in platform_reach:
            platform_reach[platform] += analytics.reach
        bucket = grouped.setdefault(
            post.id,
            {
                "post_id": post.id,
                "title": post.title,
                "platform": platform,
                "reach": 0,
                "engagements": 0,
            },
        )
        bucket["reach"] += analytics.reach
        bucket["engagements"] += analytics.likes + analytics.comments + analytics.shares

    top_posts = []
    for item in grouped.values():
        item["engagement_rate"] = round(item["engagements"] / item["reach"] * 100, 2) if item["reach"] else 0.0
        top_posts.append(item)
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
        .all()
    )
    if not rows:
        return {
            "best_day": None,
            "best_hour": None,
            "formatted_time": None,
            "confidence": 0.0,
            "sample_size": 0,
            "reason": "Not enough analytics data yet.",
        }

    buckets: dict[tuple[str, int], list[float]] = defaultdict(list)
    for analytics, post in rows:
        dt = post.scheduled_time or post.created_at or analytics.captured_at
        score = analytics.likes + analytics.comments * 2 + analytics.shares * 3
        buckets[(dt.strftime("%A"), dt.hour)].append(float(score))
    averages = {key: sum(values) / len(values) for key, values in buckets.items()}
    best_key = max(averages, key=averages.get)
    best_score = averages[best_key]
    total = sum(averages.values()) or 1
    confidence = round(min(1.0, best_score / total + min(len(rows), 20) / 40), 2)
    day, hour = best_key
    formatted = f"{(hour % 12) or 12}:00 {'AM' if hour < 12 else 'PM'}"
    return {
        "best_day": day,
        "best_hour": hour,
        "formatted_time": formatted,
        "confidence": confidence,
        "sample_size": len(rows),
        "reason": f"{day} at {formatted} has the highest average weighted engagement in your stored history.",
    }
