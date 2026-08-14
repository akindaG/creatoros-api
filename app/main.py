from app.api.routes.auth import router as auth_router
from app.api.routes.social_accounts import router as social_accounts_router

from app.api.routes.users import router as users_router
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.routes import posts


app = FastAPI(
    title="CreatorOS AI API",
    description="AI-Powered Social Growth Intelligence Platform",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(social_accounts_router)
app.include_router(users_router)
app.include_router(posts.router)


@app.get("/")
def root():
    return {
        "status": "success",
        "message": "CreatorOS AI API is running",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "creatoros-api",
    }


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
        "result": result.scalar(),
    }