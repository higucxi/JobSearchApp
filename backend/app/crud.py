from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import List, Tuple, Optional
from uuid import UUID
from .models import Job, JobSource, Application
from .schemas import JobSourceInput, ApplicationCreate, ApplicationUpdate
from .utils import normalize_company, normalize_title, is_duplicate_job
import logging

logger = logging.getLogger(__name__)

class JobCRUD:
    """CRUD operations for jobs with deduplication logic."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ingest_jobs(
            self,
            source: str,
            jobs: List[JobSourceInput]
    ) -> Tuple[int, int]:
        """
        Ingest jobs with deduplication.
        
        :param source: Where the jobs were found
        :type source: str
        :param jobs: List of the jobs being injested
        :type jobs: List[JobSourceInput]
        :return: (inserted_count, merged_count) 
                 -> total new jobs added, total jobs merged with existing ones
        :rtype: Tuple[int, int]
        """
        inserted = 0
        merged = 0

        for job_input in jobs:
            # check if this source job already exists:
            existing_source = await self._get_job_source(
                source, job_input.id
            )

            if existing_source:
                logger.info(f"Job {job_input.id} from {source} already exists")
                continue
            
            # normalize for deduplication
            norm_company = normalize_company(job_input.company)
            norm_title = normalize_title(job_input.title)

            # check for duplicate across sources
            duplicate_job = await self._find_duplicate(
                norm_company,
                norm_title,
                job_input.description
            )

            if duplicate_job:
                # Merge: add new source to existing job
                await self._add_job_source(
                    duplicate_job.id,
                    source,
                    job_input.id,
                    job_input.url
                )
                merged += 1
                logger.info(f"Merged job {job_input.id} into existing job {duplicate_job.id}")
            else:
                # insert new job
                await self._create_job(job_input, norm_company, norm_title)
                inserted += 1
                logger.info(f"Inserted new job {job_input.id}")

        await self.session.commit()

        return inserted, merged
    
    async def _get_job_source(
            self,
            source: str,
            source_job_id: str
    ) -> Optional[JobSource]:
        """Check if a job from this source already exists."""
        stmt = select(JobSource).filter(
            JobSource.source == source,
            JobSource.source_job_id == source_job_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _find_duplicate(
            self,
            norm_company: str,
            norm_title: str,
            description: str
    ) -> Optional[Job]:
        """
        Find potential duplicate jobs.
        
        First filter by normalized company and title (fast)
        Then check description similarity (slow)
        """
        # get candidates with same company and title
        stmt = select(Job).filter(
            Job.normalized_company == norm_company,
            Job.normalized_title == norm_title
        )
        result = await self.session.execute(stmt)
        candidates = result.scalars().all()

        # check each candidate for similarity
        for candidate in candidates:
            is_dup, score = is_duplicate_job(
                norm_company, norm_title, description,
                candidate.normalized_company,
                candidate.normalized_title,
                candidate.description
            )

            if is_dup:
                logger.info(f"Found duplicate with score {score:.2f}")
                return candidate
            
        return None
    
    async def _create_job(
            self,
            job_input: JobSourceInput,
            norm_company: str,
            norm_title: str
    ) -> Job:
        """Create a new job with its first source"""
        job = Job(
            normalized_company = norm_company,
            normalized_title = norm_title,
            original_title = job_input.title,
            description = job_input.description,
            location = job_input.location,
            date_posted = job_input.date_posted
        )

        self.session.add(job)
        await self.session.flush() # Get job.id

        # add source
        await self._add_job_source(
            job.id,
            job_input.source,
            job_input.id,
            job_input.url
        )

        return job
    
    async def _add_job_source(
            self,
            job_id: UUID,
            source: str,
            source_job_id: str,
            url: str
    ):
        """Add a source to an existing job."""
        job_source = JobSource(
            job_id = job_id,
            source = source,
            source_job_id = source_job_id,
            url = url
        )
        self.session.add(job_source)

    async def _get_job_by_id(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID with sources and application."""
        stmt = select(Job).filter(Job.id == job_id).options(
            selectinload(Job.sources),
            selectinload(Job.application)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

class ApplicationCRUD:
    """CRUD operations for application tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_or_update(
            self,
            job_id: UUID,
            app_data: ApplicationCreate
    ) -> Application:
        """Create or Update an Application"""
        # check if application exists
        stmt = select(Application).filter(Application.job_id == job_id)
        result = await self.session.execute(stmt)
        application = result.scalar_one_or_none()

        if application:
            # update existing
            application.status = app_data.status
            if app_data.notes is not None:
                application.notes = app_data.notes
        else:
            # create new
            application = Application(
                job_id = job_id,
                status = app_data.status,
                notes = app_data.notes
            )
            self.session.add(application)

        await self.session.commit()
        await self.session.refresh(application)

        return application
    
    async def update(
            self,
            job_id: UUID,
            app_data: ApplicationUpdate
    ) -> Optional[Application]:
        """Update application fields."""

        stmt = select(Application).filter(Application.job_id == job_id)
        result = await self.session.execute(stmt)
        application = result.scalar_one_or_none()

        if not application:
            return None

        if app_data.status:
            application.status = app_data.status
        if app_data.notes is not None:
            application.notes = app_data.notes
        
        await self.session.commit()
        await self.session.refresh(application)

        return application

    async def get_all(self) -> List[Application]:
        """Get all tracked applications."""
        stmt = select(Application).options(
            selectinload(Application.job).selectinload(Job.sources)
        ).order_by(Application.updated_at.desc())

        result = await self.session.execute(stmt)
        return result.scalars().all()
    
    async def delete(self, job_id: UUID) -> bool:
        """Delete an application."""
        stmt = select(Application).filter(Application.job_id == job_id)
        result = await self.session.execute(stmt)
        application = result.scalar_one_or_none()

        if not application:
            return False
        
        await self.session.delete(application)
        await self.session.commit()

        return True