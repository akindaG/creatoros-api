from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation
from app.services.analytics import best_posting_time, dashboard_metrics


def build_growth_recommendations(db: Session, user_id) -> dict:
    metrics = dashboard_metrics(db, user_id)
    best = best_posting_time(db, user_id)
    recs = []
    if best["best_day"]:
        recs.append({"type": "posting_time", "title": "Use your strongest posting window", "message": best["reason"]})
    else:
        recs.append({"type": "data", "title": "Collect more performance data", "message": "Add analytics snapshots for published posts so CreatorOS can identify your best posting window."})
    if metrics["engagement_rate"] < 3 and metrics["reach"] > 0:
        recs.append({"type": "engagement", "title": "Strengthen calls to action", "message": "Your aggregate engagement rate is below 3%. Test clearer questions, save prompts, and share prompts."})
    elif metrics["reach"] > 0:
        recs.append({"type": "engagement", "title": "Keep the current engagement pattern", "message": f"Your aggregate engagement rate is {metrics['engagement_rate']}%. Keep testing the formats that are already driving interactions."})
    if metrics["posts_count"] < 5:
        recs.append({"type": "consistency", "title": "Build a larger posting sample", "message": "Schedule at least five posts before making major strategy changes from the analytics."})
    return {"best_time": best, "recommendations": recs[:3]}


def persist_recommendations(db: Session, user_id, recs: list[dict]) -> None:
    for rec in recs:
        db.add(Recommendation(user_id=user_id, type=rec["type"], recommendation_text=rec["message"]))
    db.commit()
