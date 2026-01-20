from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional, Literal
from uuid import UUID

# Job Schemas
class JobSourceInput(BaseModel):
    id: str
    source: Literal["linkedin", "indeed", "greenhouse", "lever", "manual"]
    company: str
    title: str
    description: str
    location: str
    url: str
    date_posted: datetime

class JobIngestRequest(BaseModel):
    source: Literal["linkedin", "indeed", "greenhouse", "lever", "manual"]
    jobs: List[JobSourceInput]

class JobIngestResponse(BaseModel):
    inserted: int
    merged: int
    total_processed: int

class JobSourceResponse(BaseModel):
    source: str
    url: str

    model_config = ConfigDict(from_attributes=True)

class JobSearchResult(BaseModel):
    job_id: UUID
    company: str
    title: str
    location: str
    date_posted: datetime
    relevance_score: Optional[float] = None
    sources: List[JobSourceResponse]
    application_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class JobSearchResponse(BaseModel):
    results: List[JobSearchResult]
    total: int
    page: int
    page_size: int

class JobDetailResponse(BaseModel):
    job_id: UUID
    company: str
    title: str
    description: str
    location: str
    date_posted: datetime
    created_at: datetime
    sources: List[JobSourceResponse]
    application_status: Optional[str] = None
    application_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# Application Schemas
class ApplicationCreate(BaseModel):
    status: Literal["Not Applied", "Applied", "Interview", "Rejected", "Offer"]
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    status: Optional[Literal["Not Applied", "Applied", "Interview", "Rejected", "Offer"]] = None
    notes: Optional[str] = None

class ApplicationResponse(BaseModel):
    job_id: UUID
    status: str
    notes: Optional[str] = None
    updated_at: datetime
    job: JobSearchResult

    model_config = ConfigDict(from_attributes=True)