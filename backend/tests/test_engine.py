import pytest
from app.search import JobSearchEngine
from app.models import Job
from datetime import datetime, UTC, timedelta

@pytest.fixture
async def sample_jobs(async_session):
    now = datetime.now(UTC)
    jobs = [
        Job(
            original_title="Python Backend Developer",
            normalized_title="python backend developer",
            description="Build APIs using Python and FastAPI",
            normalized_company="acme",
            location="Toronto",
            date_posted=now - timedelta(days=1),
        ),
        Job(
            original_title="Senior Java Engineer",
            normalized_title="senior java engineer",
            description="Enterprise Java systems",
            normalized_company="globex",
            location="Toronto",
            date_posted=now - timedelta(days=2),
        ),
        Job(
            original_title="Junior Python Developer",
            normalized_title="junior python developer",
            description="Python scripting and automation",
            normalized_company="initech",
            location="Remote",
            date_posted=now - timedelta(days=10),
        ),
    ]

    async_session.add_all(jobs)
    await async_session.commit()

    return jobs

@pytest.mark.asyncio
async def test_search_python_relevance(async_session, sample_jobs):
    engine = JobSearchEngine(async_session)
    results, total = await engine.search(query="python")

    assert total == 2
    titles = [job.original_title for job, _ in results]
    
    assert "Python Backend Developer" in titles
    assert "Junior Python Developer" in titles

@pytest.mark.asyncio
async def test_search_exclusion(async_session, sample_jobs):
    engine = JobSearchEngine(async_session)
    results, total = await engine.search(query = "python -junior")

    titles = [job.original_title for job, _ in results]
    assert total == 1
    assert "Junior Python Developer" not in titles

@pytest.mark.asyncio
async def test_title_vs_description_weighting(async_session, sample_jobs):
    engine = JobSearchEngine(async_session)
    results, _ = await engine.search(query="backend")

    assert results[0][0].original_title == "Python Backend Developer"

@pytest.mark.asyncio
async def test_recency_boost(async_session, sample_jobs):
    engine = JobSearchEngine(async_session)

    results, _ = await engine.search(query = "python")

    assert results[0][0].date_posted > results[1][0].date_posted

@pytest.mark.asyncio
async def test_pagination(async_session, sample_jobs):
    engine = JobSearchEngine(async_session)

    results_page_1, total = await engine.search(page = 1, page_size = 1)
    results_page_2, _ = await engine.search(page = 2, page_size = 1)

    assert total >= 2
    assert results_page_1[0][0].id != results_page_2[0][0].id