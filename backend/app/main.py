from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from .database import get_db
from .schemas import (
    JobIngestRequest, JobIngestResponse,
    JobSearchResponse, JobSearchResult, JobDetailResponse,
    ApplicationCreate, ApplicationUpdate, ApplicationResponse,
    JobSourceResponse
)
from .crud import JobCRUD, ApplicationCRUD
from .search import JobSearchEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title = "Job Aggregator API",
    description = "Job application aggregation and search platform",
    version = "1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["http://localhost:3000", "http://localhost:5173"],
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Job Aggregator API",
        "version": "1.0.0",
        "endpoints": {
            "ingest": "POST /jobs/ingest",
            "search": "GET /jobs/search",
            "job_detail": "GET /jobs/{job_id}",
            "applications": "GET /applications",
            "create_applications": "POST /applications/{job_id}",
            "delete_applications": "DELETE /applications/{job_id}"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# ============================================================================
# Job Ingestion Endpoints
# ============================================================================

@app.post("/jobs/ingest", response_model = JobIngestResponse)
async def injest_jobs(
    request: JobIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest jobs from a job source with automatic deduplication

    - Detects duplicates across sources based on company + title + description
    - Merges duplicate jobs by storing all source URLs
    - Idempotent: same source job ID won't be inserted twice
    """
    try:
        crud = JobCRUD(db)
        inserted, merged = await crud.ingest_jobs(request.source, request.jobs)

        return JobIngestResponse(
            inserted = inserted,
            merged = merged,
            total_processed = len(request.jobs)
        )
    except Exception as e:
        logger.error(f"Error ingesting jobs: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))

# ============================================================================
# Search Endpoints
# ============================================================================

@app.get("/jobs/search", response_model = JobSearchResponse)
async def search_jobs(
    q: Optional[str] = Query(None, description = "Search query (supports -exclusion)"),
    company: Optional[str] = Query(None, description = "Filter by company name"),
    location: Optional[str] = Query(None, description = "Filter by location"),
    days: Optional[int] = Query(None, description = "Posted in last N days"),
    source: Optional[str] = Query(None, description = "Filter by source"),
    sort: str = Query("relevance", description = "Sort by: relevance | date"),
    page: int = Query(1, ge = 1, description = "Page number"),
    page_size: int = Query(20, ge = 1, le = 100, description = "Results per page"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search jobs with powerful filtering and relevance scoring

    Query Syntax:
    - "python": search for python
    - "python -senior": search for python, exclude senior
    - "react -remote -contract": multiple exclusions

    Scoring:
    - Title matches: 1x weight
    - Description matches: 3x weight
    - Recent posts get small boost
    - Exclusion terms hard filter results
    """
    try:
        search_engine = JobSearchEngine(db)
        results, total = await search_engine.search(
            query = q,
            company = company,
            location = location,
            days = days,
            source = source,
            sort = sort,
            page = page,
            page_size = page_size
        )

        # Convert to response format
        job_results = []
        for job, score in results:
            job_results.append(JobSearchResult(
                job_id = job.id,
                company = job.normalized_company.title(),
                title = job.original_title,
                location = job.location,
                date_posted = job.date_posted,
                relevance_score = round(score, 3) if score else None,
                sources = [
                    JobSourceResponse(source = s.source, url = s.url)
                    for s in job.sources
                ],
                application_status = job.application.status if job.application else None
            ))

        return JobSearchResponse(
            results = job_results,
            total = total,
            page = page,
            page_size = page_size
        )
    except Exception as e:
        logger.error(f"Error searching jobs: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))

@app.get("/jobs/{job_id}", response_model = JobDetailResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get full job details including description and all sources
    """
    try:
        crud = JobCRUD(db)
        job = await crud._get_job_by_id(job_id)

        if not job:
            raise HTTPException(status_code = 404, detail = "Job not found")
        
        return JobDetailResponse(
            job_id = job.id,
            company = job.normalized_company.title(),
            title = job.original_title,
            description = job.description,
            location = job.location,
            date_posted = job.date_posted,
            created_at = job.created_at,
            sources = [
                JobSourceResponse(source = s.source, url = s.url)
                for s in job.sources
            ],
            application_status = job.application.status if job.application else None,
            application_notes = job.application.notes if job.application else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))

# ============================================================================
# Application Tracking Endpoints
# ============================================================================

@app.post("/applications/{job_id}", response_model = ApplicationResponse)
async def create_or_update_application(
    job_id: UUID,
    app_data: ApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update application status for a job.
    
    Status options:
    - Not Applied
    - Applied
    - Interview
    - Rejected
    - Offer
    """
    try:
        # verify job exists
        job_crud = JobCRUD(db)
        job = await job_crud._get_job_by_id(job_id)

        if not job:
            raise HTTPException(status_code = 404, detail = "Job not found")
        
        # Create/update application
        app_crud = ApplicationCRUD(db)
        application = await app_crud.create_or_update(job_id, app_data)

        # Refresh job to get updated application
        await db.refresh(job, ['application', 'sources'])

        return ApplicationResponse(
            job_id=application.job_id,
            status=application.status,
            notes=application.notes,
            updated_at=application.updated_at,
            job=JobSearchResult(
                job_id=job.id,
                company=job.normalized_company.title(),
                title=job.original_title,
                location=job.location,
                date_posted=job.date_posted,
                sources=[
                    JobSourceResponse(source=s.source, url=s.url)
                    for s in job.sources
                ],
                application_status=application.status
            )
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))

@app.get("/applications", response_model = list[ApplicationResponse])
async def get_applications(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all tracked applications with job details
    """
    try:
        app_crud = ApplicationCRUD(db)
        applications = await app_crud.get_all()

        return [
            ApplicationResponse(
                job_id=app.job_id,
                status=app.status,
                notes=app.notes,
                updated_at=app.updated_at,
                job=JobSearchResult(
                    job_id=app.job.id,
                    company=app.job.normalized_company.title(),
                    title=app.job.original_title,
                    location=app.job.location,
                    date_posted=app.job.date_posted,
                    sources=[
                        JobSourceResponse(source=s.source, url=s.url)
                        for s in app.job.sources
                    ],
                    application_status=app.status
                )
            )
            for app in applications
        ]
    except Exception as e:
        logger.error(f"Error getting applications: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))

@app.delete("/applications/{job_id}")
async def delete_application(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an application
    """
    try:
        app_crud = ApplicationCRUD(db)
        deleted = await app_crud.delete(job_id)

        if not deleted:
            raise HTTPException(status_code = 404, detail = "Application not found")
        
        return {"message": "Application deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting application: {str(e)}")
        raise HTTPException(status_code = 500, detail = str(e))