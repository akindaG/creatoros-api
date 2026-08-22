from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes.ai import router as ai_router
from app.api.routes.analytics import router as analytics_router
from app.api.routes.auth import router as auth_router
from app.api.routes.media import router as media_router
from app.api.routes.posts import router as posts_router
from app.api.routes.publishing import router as publishing_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.scheduling import router as scheduling_router
from app.api.routes.social_accounts import router as social_accounts_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.core.database import get_db


app = FastAPI(
    title="CreatorOS AI API",
    description="AI-Powered Social Growth Intelligence Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings.media_path.mkdir(parents=True, exist_ok=True)
app.mount("/media/files", StaticFiles(directory=str(settings.media_path)), name="media")

for router in (
    auth_router,
    users_router,
    social_accounts_router,
    posts_router,
    scheduling_router,
    media_router,
    ai_router,
    analytics_router,
    recommendations_router,
    publishing_router,
):
    app.include_router(router)


@app.get("/")
def root():
    return {"status": "success", "message": "CreatorOS AI API is running", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "creatoros-api"}


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected", "result": result.scalar()}
