import pytest
from datetime import date
from app.crud import JobCRUD, ApplicationCRUD
from app.schemas import JobSourceInput, ApplicationCreate, ApplicationUpdate
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import Job, Application

@pytest.mark.asyncio
async def test_ingest_job(async_session):
    job_crud = JobCRUD(async_session)

    job = JobSourceInput(
        id="1",
        source="linkedin",
        title="Software Engineer",
        company="OpenAI",
        description="Build AI systems",
        location="Remote",
        url="https://linkedin.com/job/1",
        date_posted=date.today()
    )

    inserted, merged = await job_crud.ingest_jobs("linkedin", [job])

    assert inserted == 1
    assert merged == 0
    
    result = await async_session.execute(select(Job))
    jobs = result.scalars().all()

    assert len(jobs) == 1
    assert jobs[0].original_title == "Software Engineer"

@pytest.mark.asyncio
async def test_job_deduplication(async_session):
    job_crud = JobCRUD(async_session)

    job1 = JobSourceInput(
        id="1",
        source="linkedin",
        title="Data Engineer",
        company="Stripe",
        description="Build pipelines",
        location="Remote",
        url="x",
        date_posted=date.today()
    )

    job2 = JobSourceInput(
        id="2",
        source="indeed",
        title="Data Engineer",
        company="Stripe",
        description="Build pipelines",
        location="Remote",
        url="y",
        date_posted=date.today()
    )

    inserted, merged = await job_crud.ingest_jobs("linkedin", [job1])
    inserted2, merged2 = await job_crud.ingest_jobs("indeed", [job2])

    assert inserted == 1
    assert merged2 == 1

    result = await async_session.execute(
        select(Job).options(selectinload(Job.sources))
    )
    jobs = result.scalars().all()

    assert len(jobs) == 1
    assert len(jobs[0].sources) == 2

@pytest.mark.asyncio
async def test_create_application(async_session):
    job_crud = JobCRUD(async_session)
    app_crud = ApplicationCRUD(async_session)

    job = JobSourceInput(
        id="1",
        source="linkedin",
        title="Backend Engineer",
        company="Meta",
        description="APIs",
        location="NYC",
        url="z",
        date_posted=date.today()
    )

    await job_crud.ingest_jobs("linkedin", [job])

    result = await async_session.execute(select(Job))
    job_obj = result.scalar_one()

    app = await app_crud.create_or_update(
        job_obj.id,
        ApplicationCreate(status = "Applied", notes = "First round")
    )

    assert app.status == "Applied"
    assert app.notes == "First round"

@pytest.mark.asyncio
async def test_update_application(async_session):
    job_crud = JobCRUD(async_session)
    app_crud = ApplicationCRUD(async_session)

    job = JobSourceInput(
        id="1",
        source="linkedin",
        title="ML Engineer",
        company="OpenAI",
        description="Models",
        location="Remote",
        url="x",
        date_posted=date.today()
    )

    await job_crud.ingest_jobs("linkedin", [job])

    result = await async_session.execute(select(Job))
    job_obj = result.scalar_one()

    await app_crud.create_or_update(
        job_obj.id,
        ApplicationCreate(status="Applied")
    )

    updated = await app_crud.update(
        job_obj.id,
        ApplicationUpdate(status="Interview")
    )

    assert updated.status == "Interview"

@pytest.mark.asyncio
async def test_delete_application(async_session):
    job_crud = JobCRUD(async_session)
    app_crud = ApplicationCRUD(async_session)

    job = JobSourceInput(
        id="1",
        source="linkedin",
        title="Backend Engineer",
        company="Stripe",
        description="APIs",
        location="Remote",
        url="y",
        date_posted=date.today()
    )

    await job_crud.ingest_jobs("linkedin", [job])

    result = await async_session.execute(select(Job))
    job_obj = result.scalar_one()

    await app_crud.create_or_update(
        job_obj.id,
        ApplicationCreate(status="Applied")
    )

    deleted = await app_crud.delete(job_obj.id)

    assert deleted is True