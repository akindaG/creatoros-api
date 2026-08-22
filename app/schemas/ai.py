from typing import Optional

from pydantic import BaseModel, Field


class CaptionRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=300)
    description: Optional[str] = None
    tone: str = "professional"
    platform: str = "instagram"


class CaptionResponse(BaseModel):
    caption: str
    cta: str
    hashtags: list[str]
    source: str


class HashtagRequest(BaseModel):
    topic: str
    caption: Optional[str] = None
    platform: str = "instagram"


class HashtagResponse(BaseModel):
    hashtags: list[str]
    source: str


class AnalyzeRequest(BaseModel):
    caption: str = Field(min_length=1)
    platform: str = "instagram"


class AnalyzeResponse(BaseModel):
    score: int
    strengths: list[str]
    suggestions: list[str]
    source: str
