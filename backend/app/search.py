from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, UTC
from typing import List, Optional
from .models import Job, JobSource, Application
from .utils import extract_exclusion_terms, tokenize_for_search
import math

class JobSearchEngine:
    """
    Search engine with relevance scoring and exclusion support.

    Scoring Algorithm:
    - Title matches: weight = 1.0
    - Description matches: weight = 3.0
    - Term Frequency (TF) considered
    - Recency boost: jobs posted in the last 7 days get small boost
    - Exclusion terms: hard filter, removes results even with high relevance
    """

    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def search(
            self,
            query: Optional[str] = None,
            company: Optional[str] = None,
            location: Optional[str] = None,
            days: Optional[int] = None,
            source: Optional[str] = None,
            sort: str = "relevance",
            page: int = 1,
            page_size: int = 20
    ) -> tuple:
        """
        Execute search with filters and return scored results

        returns (results, total_count)
        """
        # Parse query for exclusions
        exclusion_terms = []
        search_terms = []

        if query:
            cleaned_query, exclusion_terms = extract_exclusion_terms(query)
            search_terms = tokenize_for_search(cleaned_query)
        
        # build base query
        stmt = select(Job).options(
            selectinload(Job.sources),
            selectinload(Job.application)
        )

        # apply filters
        filters = []

        # company filter
        if company:
            filter.append(Job.normalized_company.ilike(f"%{company.lower()}%"))

        # location filter
        if location:
            filter.append(Job.location.ilike(f"%{location.lower()}%"))
        
        # date filter
        if days:
            cutoff_date = datetime.now(UTC) - timedelta(days = days)
            filter.append(Job.date_posted >= cutoff_date)

        # source filter
        if source:
            stmt = stmt.join(JobSource).filter(JobSource.source == source)
        
        if filters:
            stmt = stmt.filter(and_(*filters))

        # get all matching jobs for scoring
        result = await self.session.execute(stmt)
        jobs = result.scalars().unique().all()

        # score and filter jobs
        scored_jobs = []
        for job in jobs:
            # calculate relevance score
            score = self._calculate_relevance(
                job, search_terms, exclusion_terms
            )

            # exclude if contains exclusion terms of no match
            if score is None:
                continue

            scored_jobs.append((job, score))
        
        total = len(scored_jobs)

        # sort results
        if sort == "relevance" and search_terms:
            # greatest to least relevance score sort
            scored_jobs.sort(key = lambda x: x[1], reverse = True)
        else:
            # sort from soonest to oldest dates
            # default to date if no search terms
            scored_jobs.sort(key = lambda x: x[0].date_posted, reverse = True)

        # paginate
        offset = (page - 1) * page_size
        paginated = scored_jobs[offset:offset + page_size]

        return paginated, total
            
        
    def _calculate_relevance(
            self,
            job: Job,
            search_terms: List[str],
            exclusion_terms: List[str]
    ) -> Optional[float]:
        """
        Calculate relevance score for a job.

        Returns None if job should be excluded.
        """
        # if no search terms, return date-based score
        if not search_terms:
            return self._get_recency_boost(job.date_posted)
        
        # check exclusion terms first (hard filter)
        if exclusion_terms:
            job_text = f"{job.original_title} {job.description}".lower()
            
            for term in exclusion_terms:
                if term in job_text:
                    return None # exclude this job
        
        # tokenize job fields
        title_tokens = tokenize_for_search(job.original_title)
        desc_tokens = tokenize_for_search(job.description)

        title_score = 0.0
        desc_score = 0.0

        # calculate TF for each search term
        for term in search_terms:
            # title matches (weight = 1.0)
            title_tf = title_tokens.count(term)
            if title_tf > 0:
                # diminishing returns for multiple occurences
                title_score += 1.0 * math.log(1 + title_tf)
            
            # description matches (weight = 3.0)
            desc_tf = desc_tokens.count(term)
            if desc_tf > 0:
                desc_score += 3.0 * math.log(1 + desc_tf)
        
        # combined score
        relevance = title_score + desc_score

        # no matches at all
        if relevance == 0:
            return None
        
        # normalize by query length
        relevance = relevance / len(search_terms)

        # add recency boost
        recency_boost = self._get_recency_boost(job.date_posted)
        relevance += recency_boost

        return relevance

    def _get_recency_boost(self, date_posted: datetime) -> float:
        """
        Small boost for recent postings.
        Jobs in last 7 days get up to 0.5 boost.
        """
        days_ago = (datetime.now(UTC) - date_posted).days

        if days_ago <= 7:
            return 0.5 * (1 - days_ago / 7)

        return 0.0
