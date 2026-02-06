import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, UTC
import uuid

from app.main import app
from app.database import get_db

@pytest.fixture
async def client(async_session):
    async def override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()

@pytest.fixture
def sample_jobs():
    """Sample job data for testing."""
    return [
        {
            "id": "1",
            "source": "linkedin",
            "company": "Google LLC",
            "title": "Software Engineer",
            "description": "Build scalable systems with Python and Go. Work on distributed systems and cloud infrastructure.",
            "location": "Mountain View, CA",
            "url": "https://linkedin.com/jobs/001",
            "date_posted": "2025-01-01T10:00:00Z"
        },
        {
            "id": "2",
            "source": "indeed",
            "company": "Meta",
            "title": "Senior Software Engineer",
            "description": "Lead development of React applications. Senior-level position requiring 5+ years experience.",
            "location": "Menlo Park, CA",
            "url": "https://indeed.com/jobs/002",
            "date_posted": "2024-12-28T14:30:00Z"
        },
        {
            "id": "3",
            "source": "greenhouse",
            "company": "Stripe Inc",
            "title": "Backend Engineer",
            "description": "Build payment APIs with Ruby and Python. Work on distributed systems.",
            "location": "San Francisco, CA (Remote OK)",
            "url": "https://stripe.com/jobs/003",
            "date_posted": "2025-01-02T09:00:00Z"
        }
    ]

###############################################################################################################
class TestRootEndpoints:
    """Test root and health check endpoints."""
    
    @pytest.mark.asyncio
    async def test_root(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

###############################################################################################################
class TestJobIngestion:
    """Test job ingestion endpoints."""
    
    @pytest.mark.asyncio
    async def test_ingest_single_job(self, client, sample_jobs):
        payload = {
            "source": "manual",
            "jobs": [sample_jobs[0]]
        }
        
        response = await client.post("/jobs/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["inserted"] == 1
        assert data["merged"] == 0
        assert data["total_processed"] == 1
    
    @pytest.mark.asyncio
    async def test_ingest_multiple_jobs(self, client, sample_jobs):
        payload = {
            "source": "manual",
            "jobs": sample_jobs
        }
        
        response = await client.post("/jobs/ingest", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data["inserted"] == 3
        assert data["merged"] == 0
        assert data["total_processed"] == 3
    
    @pytest.mark.asyncio
    async def test_ingest_duplicate_same_source(self, client, sample_jobs):
        payload = {
            "source": "linkedin",
            "jobs": [sample_jobs[0]]
        }
        
        # First ingestion
        response1 = await client.post("/jobs/ingest", json=payload)
        assert response1.status_code == 200
        assert response1.json()["inserted"] == 1
        
        # Second ingestion - same source, same ID
        response2 = await client.post("/jobs/ingest", json=payload)
        assert response2.status_code == 200
        data = response2.json()
        assert data["inserted"] == 0  # Should not insert again
        assert data["merged"] == 0    # Should not merge (same source)
    
    @pytest.mark.asyncio
    async def test_ingest_duplicate_different_source(self, client):
        # First ingestion from LinkedIn
        payload1 = {
            "source": "linkedin",
            "jobs": [{
                "id": "google-001",
                "source": "linkedin",
                "company": "Google LLC",
                "title": "Software Engineer",
                "description": "Build systems",
                "location": "Mountain View, CA",
                "url": "https://linkedin.com/jobs/google-001",
                "date_posted": "2025-01-01T10:00:00Z"
            }]
        }
        
        response1 = await client.post("/jobs/ingest", json=payload1)
        assert response1.status_code == 200
        assert response1.json()["inserted"] == 1
        
        # Second ingestion from Indeed - same job, different source
        payload2 = {
            "source": "indeed",
            "jobs": [{
                "id": "google-002",
                "source": "indeed",
                "company": "Google Inc",  # Different name variant
                "title": "SWE",            # Different title variant
                "description": "Build systems",
                "location": "Mountain View, CA",
                "url": "https://indeed.com/jobs/google-002",
                "date_posted": "2025-01-01T10:00:00Z"
            }]
        }
        
        response2 = await client.post("/jobs/ingest", json=payload2)
        assert response2.status_code == 200
        data = response2.json()
        assert data["inserted"] == 0  # Should not insert new job
        assert data["merged"] == 1    # Should merge into existing job
    
    @pytest.mark.asyncio
    async def test_ingest_invalid_payload(self, client):
        # Missing required fields
        payload = {
            "source": "manual",
            "jobs": [{
                "id": "bad-job",
                "company": "Test"
                # Missing title, description, etc.
            }]
        }
        
        response = await client.post("/jobs/ingest", json=payload)
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_ingest_invalid_source(self, client, sample_jobs):
        payload = {
            "source": "invalid_source",  # Not in allowed list
            "jobs": [sample_jobs[0]]
        }
        
        response = await client.post("/jobs/ingest", json=payload)
        assert response.status_code == 422  # Validation error

###############################################################################################################
class TestJobSearch:
    """Test job search endpoints."""
    
    @pytest.mark.asyncio
    async def test_search_all_jobs(self, client, sample_jobs):
        # First ingest some jobs
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        # Search without filters
        response = await client.get("/jobs/search")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 3
        assert len(data["results"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
    
    @pytest.mark.asyncio
    async def test_search_with_query(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        # Search for "python"
        response = await client.get("/jobs/search?q=python")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] >= 1  # At least one job mentions Python
        
        # Verify results have relevance scores when searching
        for job in data["results"]:
            assert job["relevance_score"] is not None
    
    @pytest.mark.asyncio
    async def test_search_with_exclusions(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        # Search for jobs but exclude "senior"
        response = await client.get("/jobs/search?q=engineer%20-senior")
        assert response.status_code == 200
        
        data = response.json()
        # Should not include the "Senior Software Engineer" job
        for job in data["results"]:
            assert "senior" not in job["title"].lower()
    
    @pytest.mark.asyncio
    async def test_search_by_company(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        response = await client.get("/jobs/search?company=Google")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert "google" in data["results"][0]["company"].lower()
    
    @pytest.mark.asyncio
    async def test_search_by_location(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        response = await client.get("/jobs/search?location=Remote")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] >= 1
        for job in data["results"]:
            assert "remote" in job["location"].lower()
    
    @pytest.mark.asyncio
    async def test_search_by_days(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        # Search for jobs posted in last 7 days
        response = await client.get("/jobs/search?days=7")
        assert response.status_code == 200
        
        data = response.json()
        # Should only include recent jobs
        cutoff = datetime.now(UTC) - timedelta(days=7)
        for job in data["results"]:
            job_date = datetime.fromisoformat(job["date_posted"].replace("Z", "+00:00"))
            assert job_date >= cutoff
    
    @pytest.mark.asyncio
    async def test_search_sort_by_date(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        response = await client.get("/jobs/search?sort=date")
        assert response.status_code == 200
        
        data = response.json()
        # Verify sorted by date descending (newest first)
        dates = [datetime.fromisoformat(job["date_posted"].replace("Z", "+00:00")) 
                 for job in data["results"]]
        assert dates == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_search_sort_by_relevance(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        response = await client.get("/jobs/search?q=python&sort=relevance")
        assert response.status_code == 200
        
        data = response.json()
        # Verify sorted by relevance descending
        scores = [job["relevance_score"] for job in data["results"] if job["relevance_score"]]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_search_pagination(self, client):
        # Create many jobs for pagination testing
        jobs = []
        for i in range(25):
            jobs.append({
                "id": f"job-{i:03d}",
                "source": "manual",
                "company": f"Company {i}",
                "title": f"Engineer {i}",
                "description": "Test job description",
                "location": "Remote",
                "url": f"https://example.com/{i}",
                "date_posted": "2025-01-01T10:00:00Z"
            })
        
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": jobs})
        
        # Get page 1
        response1 = await client.get("/jobs/search?page=1&page_size=20")
        assert response1.status_code == 200
        data1 = response1.json()
        assert len(data1["results"]) == 20
        assert data1["total"] == 25
        
        # Get page 2
        response2 = await client.get("/jobs/search?page=2&page_size=20")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["results"]) == 5
        
        # Verify no overlap
        ids_page1 = {job["job_id"] for job in data1["results"]}
        ids_page2 = {job["job_id"] for job in data2["results"]}
        assert len(ids_page1.intersection(ids_page2)) == 0
    
    @pytest.mark.asyncio
    async def test_search_empty_results(self, client, sample_jobs):
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        response = await client.get("/jobs/search?q=nonexistentquery12345")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 0
        assert len(data["results"]) == 0

###############################################################################################################
class TestJobDetail:
    """Test job detail endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_job_by_id(self, client, sample_jobs):
        # Ingest a job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Search to get the job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Get job details
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["job_id"] == job_id
        assert "company" in data
        assert "title" in data
        assert "description" in data
        assert "location" in data
        assert "sources" in data
        assert len(data["sources"]) >= 1
    
    @pytest.mark.asyncio
    async def test_get_job_invalid_id(self, client):
        fake_uuid = str(uuid.uuid4())
        response = await client.get(f"/jobs/{fake_uuid}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_get_job_with_application(self, client, sample_jobs):
        # Ingest job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Get job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Track application
        await client.post(f"/applications/{job_id}", json={
            "status": "Applied",
            "notes": "Test notes"
        })
        
        # Get job details - should include application info
        response = await client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["application_status"] == "Applied"
        assert data["application_notes"] == "Test notes"

###############################################################################################################
class TestApplicationTracking:
    """Test application tracking endpoints."""
    
    @pytest.mark.asyncio
    async def test_create_application(self, client, sample_jobs):
        # Ingest job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Get job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Create application
        response = await client.post(f"/applications/{job_id}", json={
            "status": "Applied",
            "notes": "Applied via referral"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "Applied"
        assert data["notes"] == "Applied via referral"
        assert "job" in data
    
    @pytest.mark.asyncio
    async def test_update_application(self, client, sample_jobs):
        # Ingest job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Get job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Create application
        response1 = await client.post(f"/applications/{job_id}", json={
            "status": "Applied",
            "notes": "First note"
        })
        assert response1.status_code == 200
        
        # Update application
        response2 = await client.post(f"/applications/{job_id}", json={
            "status": "Interview",
            "notes": "Updated note"
        })
        assert response2.status_code == 200
        
        data = response2.json()
        assert data["status"] == "Interview"
        assert data["notes"] == "Updated note"
    
    @pytest.mark.asyncio
    async def test_create_application_invalid_job(self, client):
        fake_uuid = str(uuid.uuid4())
        response = await client.post(f"/applications/{fake_uuid}", json={
            "status": "Applied",
            "notes": "Test"
        })
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_all_applications(self, client, sample_jobs):
        # Ingest jobs
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": sample_jobs})
        
        # Get job IDs
        search_response = await client.get("/jobs/search")
        job_ids = [job["job_id"] for job in search_response.json()["results"]]
        
        # Track applications for 2 jobs
        await client.post(f"/applications/{job_ids[0]}", json={
            "status": "Applied",
            "notes": "Job 1"
        })
        await client.post(f"/applications/{job_ids[1]}", json={
            "status": "Interview",
            "notes": "Job 2"
        })
        
        # Get all applications
        response = await client.get("/applications")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 2
        
        # Verify both applications are present
        statuses = {app["status"] for app in data}
        assert "Applied" in statuses
        assert "Interview" in statuses
    
    @pytest.mark.asyncio
    async def test_get_applications_empty(self, client):
        response = await client.get("/applications")
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_delete_application(self, client, sample_jobs):
        # Ingest job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Get job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Create application
        await client.post(f"/applications/{job_id}", json={
            "status": "Applied",
            "notes": "Test"
        })
        
        # Verify it exists
        apps_response = await client.get("/applications")
        assert len(apps_response.json()) == 1
        
        # Delete application
        delete_response = await client.delete(f"/applications/{job_id}")
        assert delete_response.status_code == 200
        
        # Verify it's deleted
        apps_response2 = await client.get("/applications")
        assert len(apps_response2.json()) == 0
    
    @pytest.mark.asyncio
    async def test_delete_application_not_found(self, client):
        fake_uuid = str(uuid.uuid4())
        response = await client.delete(f"/applications/{fake_uuid}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_application_status_validation(self, client, sample_jobs):
        # Ingest job
        await client.post("/jobs/ingest", json={"source": "manual", "jobs": [sample_jobs[0]]})
        
        # Get job ID
        search_response = await client.get("/jobs/search")
        job_id = search_response.json()["results"][0]["job_id"]
        
        # Try invalid status
        response = await client.post(f"/applications/{job_id}", json={
            "status": "InvalidStatus",
            "notes": "Test"
        })
        assert response.status_code == 422  # Validation error

###############################################################################################################


class TestIntegrationScenarios:
    """Test complete user workflows."""
    
    @pytest.mark.asyncio
    async def test_full_job_search_workflow(self, client, sample_jobs):
        """Test: User ingests jobs, searches, views details, tracks application."""
        
        # 1. Ingest jobs
        ingest_response = await client.post("/jobs/ingest", json={
            "source": "manual",
            "jobs": sample_jobs
        })
        assert ingest_response.status_code == 200
        assert ingest_response.json()["inserted"] == 3
        
        # 2. Search for jobs
        search_response = await client.get("/jobs/search?q=engineer")
        assert search_response.status_code == 200
        assert search_response.json()["total"] >= 1
        
        # 3. Get job details
        job_id = search_response.json()["results"][0]["job_id"]
        detail_response = await client.get(f"/jobs/{job_id}")
        assert detail_response.status_code == 200
        
        # 4. Track application
        app_response = await client.post(f"/applications/{job_id}", json={
            "status": "Applied",
            "notes": "Looks great!"
        })
        assert app_response.status_code == 200
        
        # 5. View applications
        apps_response = await client.get("/applications")
        assert apps_response.status_code == 200
        assert len(apps_response.json()) == 1
        
        # 6. Update application status
        update_response = await client.post(f"/applications/{job_id}", json={
            "status": "Interview",
            "notes": "Got interview!"
        })
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "Interview"
    
    @pytest.mark.asyncio
    async def test_deduplication_across_sources(self, client):
        """Test: Same job from different sources gets merged."""
        
        # Ingest from LinkedIn
        await client.post("/jobs/ingest", json={
            "source": "linkedin",
            "jobs": [{
                "id": "linkedin-001",
                "source": "linkedin",
                "company": "Google LLC",
                "title": "Software Engineer",
                "description": "Build stuff",
                "location": "MTV",
                "url": "https://linkedin.com/1",
                "date_posted": "2025-01-01T10:00:00Z"
            }]
        })
        
        # Ingest same job from Indeed
        response = await client.post("/jobs/ingest", json={
            "source": "indeed",
            "jobs": [{
                "id": "indeed-001",
                "source": "indeed",
                "company": "Google Inc",  # Variant name
                "title": "SWE",            # Variant title
                "description": "Build stuff",
                "location": "MTV",
                "url": "https://indeed.com/1",
                "date_posted": "2025-01-01T10:00:00Z"
            }]
        })
        
        # Should merge, not insert
        assert response.json()["merged"] == 1
        assert response.json()["inserted"] == 0
        
        # Verify only 1 job exists with 2 sources
        search_response = await client.get("/jobs/search?company=google")
        results = search_response.json()["results"]
        assert len(results) == 1
        assert len(results[0]["sources"]) == 2
        
        source_names = {s["source"] for s in results[0]["sources"]}
        assert "linkedin" in source_names
        assert "indeed" in source_names