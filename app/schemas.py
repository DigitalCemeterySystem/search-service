from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["pending", "running", "succeeded", "failed"]


class SearchRequest(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    birth_date: str | None = Field(default=None, max_length=40)
    death_date: str | None = Field(default=None, max_length=40)
    cemetery: str | None = Field(default=None, max_length=160)
    extra_terms: str | None = Field(default=None, max_length=300)
    limit: int = Field(default=5, ge=1, le=10)


class SearchResultLink(BaseModel):
    url: str
    title: str | None = None


class LogEntry(BaseModel):
    timestamp: datetime
    stage: str
    level: Literal["info", "success", "warning", "error"]
    message: str


class RelevantInfoRecord(BaseModel):
    id: int
    full_name: str
    query: str
    request: dict[str, Any]
    urls: list[SearchResultLink]
    relevant_preview: str
    relevant_text_length: int
    created_at: datetime


class RelevantInfoRecordDetail(RelevantInfoRecord):
    relevant_text: str


class SearchJobResponse(BaseModel):
    id: str
    status: JobStatus
    stage: str
    request: dict[str, Any]
    query: str | None = None
    urls: list[SearchResultLink] = Field(default_factory=list)
    record_id: int | None = None
    relevant_preview: str | None = None
    relevant_text_length: int = 0
    logs: list[LogEntry] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: str
