import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.analytics import Analytics
from app.models.post import Post
from app.models.user import User
from app.schemas.analytics import AnalyticsSnapshotCreate, AnalyticsSnapshotResponse, DashboardAnalytics
from app.services.analytics import dashboard_metrics


router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.post("/posts/{post_id}", response_model=AnalyticsSnapshotResponse, status_code=201)
def create_snapshot(post_id: UUID, data: AnalyticsSnapshotCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    interactions = data.likes + data.comments + data.shares
    engagement_rate = round(interactions / data.reach * 100, 2) if data.reach else 0.0
    row = Analytics(post_id=post.id, followers=data.followers, reach=data.reach, likes=data.likes, comments=data.comments, shares=data.shares, engagement_rate=engagement_rate)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/dashboard", response_model=DashboardAnalytics)
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return dashboard_metrics(db, current_user.id)


@router.get("/posts/{post_id}", response_model=list[AnalyticsSnapshotResponse])
def post_analytics(post_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    post = db.query(Post).filter(Post.id == post_id, Post.user_id == current_user.id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return db.query(Analytics).filter(Analytics.post_id == post.id).order_by(Analytics.captured_at.asc()).all()


@router.get("/report")
def export_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    metrics = dashboard_metrics(db, current_user.id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in metrics.items():
        writer.writerow([key, value])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=creatoros-analytics.csv"})
