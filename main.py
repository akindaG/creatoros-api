from fastapi import FastAPI

app = FastAPI(
    title="CreatorOS AI API",
    description="AI-Powered Social Growth Intelligence Platform",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {
        "message": "CreatorOS AI API is running",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "creatoros-api",
    }