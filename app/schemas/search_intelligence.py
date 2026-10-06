from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class SearchAuditRequest(BaseModel):
    url: HttpUrl


class SearchIssue(BaseModel):
    severity: Literal["info", "warning", "critical"]
    category: str
    message: str


class SearchPageInfo(BaseModel):
    status_code: int
    final_url: str
    title: Optional[str] = None
    meta_description: Optional[str] = None
    canonical_url: Optional[str] = None
    robots: Optional[str] = None
    h1: list[str] = Field(default_factory=list)
    h2_count: int = 0
    h3_count: int = 0
    word_count: int = 0
    internal_links: int = 0
    external_links: int = 0
    images: int = 0
    images_with_alt: int = 0
    structured_data_blocks: int = 0
    author_signal: bool = False
    open_graph_signal: bool = False


class SearchScoreBreakdown(BaseModel):
    technical_seo: int
    content_quality: int
    answer_clarity: int
    structured_content: int
    authority_signals: int
    discoverability: int


class SearchAuditResponse(BaseModel):
    url: str
    score: int
    scores: SearchScoreBreakdown
    page: SearchPageInfo
    issues: list[SearchIssue]
    recommendations: list[str]
    methodology: str
    source: str
