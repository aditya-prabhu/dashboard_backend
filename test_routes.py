import pytest
import httpx
from main import app

@pytest.mark.asyncio
async def test_get_projects(monkeypatch):
    async def mock_fetch_project_names():
        return ["CHMP", "OnboardMe"]
    monkeypatch.setattr("app.utils.fetch_data.fetch_project_names", mock_fetch_project_names)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/projects")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_get_releases(monkeypatch):
    async def mock_fetch_releases(project):
        return [
            {"id": "1", "name": "Sprint 1", "attributes": {"startDate": "2024-01-01", "finishDate": "2024-01-15", "timeFrame": "current"}},
            {"id": "2", "name": "Sprint 2", "attributes": {"startDate": "2024-01-16", "finishDate": "2024-01-31", "timeFrame": "past"}}
        ], None
    monkeypatch.setattr("app.utils.fetch_data.fetch_releases", mock_fetch_releases)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/releases", params={"project": "CHMP"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_get_pipeline_data(monkeypatch):
    async def mock_fetch_pipeline_releases(start, end, project):
        return [
            {
                "id": 1,
                "releaseDefinition": {"id": 10, "name": "Pipe", "path": "/"},
                "status": "active",
                "createdOn": "2024-01-01T00:00:00Z",
                "description": "desc"
            }
        ], None
    monkeypatch.setattr("app.utils.fetch_data.fetch_pipeline_releases", mock_fetch_pipeline_releases)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/pipelines", params={
            "startDate": "2024-01-01",
            "endDate": "2024-01-31",
            "project": "CHMP"
        })
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_get_iteration_work_items(monkeypatch):
    async def mock_fetch_iteration_work_items(iteration_id, project):
        return [
            {"source": {"id": 1}, "target": {"id": 2}}
        ], None
    async def mock_fetch_work_items(ids, project):
        return [
            {"id": 1, "fields": {"System.AreaPath": "A", "System.IterationPath": "I", "System.AssignedTo": {"displayName": "User"}, "System.Title": "T", "System.State": "Active"}},
            {"id": 2, "fields": {"System.AreaPath": "A", "System.IterationPath": "I", "System.AssignedTo": "User2", "System.Title": "T2", "System.State": "Closed"}}
        ], None
    monkeypatch.setattr("app.utils.fetch_data.fetch_iteration_work_items", mock_fetch_iteration_work_items)
    monkeypatch.setattr("app.utils.fetch_data.fetch_work_items", mock_fetch_work_items)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/iteration-work-items", params={
            "iteration_id": "123",
            "project": "CHMP"
        })
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert all("id" in item for item in resp.json())

@pytest.mark.asyncio
async def test_create_project(monkeypatch, tmp_path):
    # Mock helpers to use tmp_path for file operations
    def mock_create_project_directory_and_urls(project_name, pipelines, releases):
        d = tmp_path / project_name
        d.mkdir()
        with open(d / "urls.json", "w") as f:
            f.write("{}")
    def mock_append_project_to_projects_json(project_name, path, team_name):
        f = tmp_path / "projects.json"
        projects = []
        if f.exists():
            import json
            with open(f, "r") as file:
                projects = json.load(file)
        projects.append({"projectName": project_name, "path": path, "teamName": team_name})
        with open(f, "w") as file:
            import json
            json.dump(projects, file)
    monkeypatch.setattr("app.utils.form_utils.create_project_directory_and_urls", mock_create_project_directory_and_urls)
    monkeypatch.setattr("app.utils.form_utils.append_project_to_projects_json", mock_append_project_to_projects_json)
    payload = {
        "project_name": "TestProj",
        "pipelines": ["p1"],
        "releases": ["r1"],
        "teamName": "Team",
        "path": "TestProj"
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/create-project", json=payload)
    assert resp.status_code == 200
    assert resp.json()["success"]

@pytest.mark.asyncio
async def test_get_project_info(monkeypatch):
    # Mock file reads
    def mock_open_urls(*args, **kwargs):
        from io import StringIO
        return StringIO('{"pipelines": ["p1"], "releases": ["r1"]}')
    def mock_open_projects(*args, **kwargs):
        from io import StringIO
        return StringIO('[{"projectName": "TestProj", "path": "TestProj", "teamName": "Team"}]')
    monkeypatch.setattr("builtins.open", lambda f, mode="r": mock_open_urls() if "urls.json" in f else mock_open_projects())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/project-info", params={"project_name": "TestProj"})
    assert resp.status_code == 200
    data = resp.json()
    assert "urls" in data and "project" in data