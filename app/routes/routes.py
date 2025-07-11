from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import os
import json
import re
import urllib.parse
from dateutil.parser import parse as parse_datetime
from app.utils.fetch_data import (
    fetch_pipeline_releases, fetch_iterations,
    # fetch_wiql_url, fetch_release_plan_work_items
    fetch_iteration_work_items, fetch_work_items,
    fetch_project_names, fetch_pipeline_releases_by_definition,
    fetch_wiki_pages, fetch_release_work_items,
    fetch_release_definition, fetch_pending_approvals_from_pipelines,
    fetch_release_plan, fetch_azure_url, fetch_test_plan_runs,
    fetch_test_run_results
)
from app.utils.form_utils import (
    ProjectCreateRequest,
    create_project_directory,
    append_project_to_projects_json
)

router = APIRouter()

@router.get("/api/projects",
    description="Fetches the list of available projects",
    response_description="List of project names",
    responses={
        200: {
            "description": "List of project names",
            "content": {
                "application/json": {
                    "example": [
                        "CHMP",
                        "OnboardMe",
                    ]
                }
            }
        }
    }
)
async def get_projects():
    try:
        projects = fetch_project_names()
        return JSONResponse(content=projects)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/iterations",
    description="Fetches release data for current and past iterations",
    response_description="List of releases with their details",
    responses={
        200: {
            "description": "List of releases with their details",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "192286be-14c2-4af5-8b9f-7d38fce4d17a",
                            "name": "Sprint 13",
                            "startDate": "2024-05-01T00:00:00Z",
                            "finishDate": "2024-05-15T23:59:59Z",
                            "ReleaseNotesUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_wiki/wikis/ReleaseNotes/123"
                        },
                        {
                            "id": "85c16209-af6f-4520-a6ad-575c91c71e36",
                            "name": "Sprint 12",
                            "startDate": "2024-04-15T00:00:00Z",
                            "finishDate": "2024-04-30T23:59:59Z",
                            "ReleaseNotesUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_wiki/wikis/ReleaseNotes/122"
                        }
                    ]
                }
            }
        }
    }
)
async def get_iterations(
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    iterations, error = fetch_iterations(project)
    if error:
        raise HTTPException(status_code=500, detail=error)
    
    filtered_iterations = [
        it for it in iterations
        if it.get("attributes", {}).get("timeFrame") in ["current", "past"]
    ]
    release_data = [
        {
            "id": it["id"],
            "name": it["name"],
            "startDate": it["attributes"]["startDate"],
            "finishDate": it["attributes"]["finishDate"]
        }
        for it in filtered_iterations[-10:]
    ]
    release_data = list(reversed(release_data))

    wiki_result, error = fetch_wiki_pages(project)
    wiki_pages = []
    if not error and wiki_result and "subPages" in wiki_result:
        wiki_pages = [
            page for page in wiki_result["subPages"]
            if "order" in page and "path" in page and "remoteUrl" in page
            and "hotfix" not in page["path"].lower()
        ]
        wiki_pages = sorted(wiki_pages, key=lambda x: x["order"])

    for release in release_data:
        release["ReleaseNotesUrl"] = None
        matched = False
        for wiki in wiki_pages:
            decoded_path = urllib.parse.unquote(wiki["path"])
            if release["name"].lower().replace(" ", "") in decoded_path.lower().replace(" ", ""):
                release["ReleaseNotesUrl"] = wiki["remoteUrl"]
                matched = True
                break
        if not matched and wiki_pages:
            remote_url = wiki_pages[0]["remoteUrl"]
            if "%2F" in remote_url:
                release["ReleaseNotesUrl"] = remote_url.rsplit("%2F", 1)[0]
            else:
                release["ReleaseNotesUrl"] = remote_url

    return JSONResponse(content=release_data)


@router.get("/api/pipelines",
    description="Fetches pipeline data for releases within a specified date range",
    response_description="List of pipelines with their details",
    responses={
        200: {
            "description": "List of pipelines with their details",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "releaseId": 12345,
                            "definitionId": 678,
                            "name": "CHMP - UI Release",
                            "path": "\\CHMP\\UI",
                            "status": "active",
                            "createdOn": "2024-06-01T12:00:00Z",
                            "description": "Release for UI changes",
                            "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=678",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12345"
                        },
                        {
                            "releaseId": 12346,
                            "definitionId": 679,
                            "name": "CHMP - API Release",
                            "path": "\\CHMP\\API",
                            "status": "completed",
                            "createdOn": "2024-05-15T09:30:00Z",
                            "description": "Release for API updates",
                            "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=679",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12346"
                        }
                    ]
                }
            }
        }
    }
)
async def get_pipeline_data(
    startDate: str = Query(..., description="Start date"),
    endDate: str = Query(..., description="End date"),
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    if not startDate or not endDate:
        raise HTTPException(status_code=400, detail="Missing start or end date")
    data, error = fetch_pipeline_releases(startDate, endDate, project)
    if error:
        raise HTTPException(status_code=500, detail=error)
    result = [
        {
            "releaseId": item["id"],
            "definitionId": item["releaseDefinition"]["id"],
            "name": item["releaseDefinition"]["name"],
            "path": item["releaseDefinition"]["path"],
            "status": item["status"],
            "createdOn": item["createdOn"],
            "description": item.get("description", "—"),
            "pipelineUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={item['releaseDefinition']['id']}",
            "releaseUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={item['id']}"
        }
        for item in data
    ]
    return JSONResponse(content=result)


@router.get("/api/pipelines-runs",
    description="Fetches pipeline data for a specific definitionId within a specified date range",
    response_description="List of pipelines with their details",
    responses={
        200: {
            "description": "List of pipelines with their details",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "releaseId": 12345,
                            "pipelineName": "CHMP - UI Release",
                            "releaseName": "Release-15",
                            "environment": "Dev",
                            "status": "succeeded",
                            "queuedOn": "2024-06-01T12:00:00Z",
                            "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=679",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12345",
                            "commitUrl": "https://github.com/PSJH/AT_MCE_CHMP/commit/debfd1e9b43735a5696cb5c478fddfcb834d0310"
                        }
                    ]
                }
            }
        }
    }
)
async def get_pipeline_runs(
    startDate: str = Query(..., description="Start date"),
    endDate: str = Query(..., description="End date"),
    project: str = Query(..., description="Project name, e.g., 'CHMP'"),
    definitionId: int = Query(..., description="Pipeline definition ID")
):
    if not startDate or not endDate:
        raise HTTPException(status_code=400, detail="Missing start or end date")
    from app.utils.fetch_data import fetch_pipeline_releases_by_definition
    data, error = fetch_pipeline_releases_by_definition(startDate, endDate, project, definitionId)
    if error:
        raise HTTPException(status_code=500, detail=error)
    result = []
    for item in data:
        commit_url = None
        for artifact in item["release"]["artifacts"]:
            def_ref = artifact["definitionReference"]
            repo = def_ref["repository"]
            provider = def_ref["repository.provider"]
            provider_id = provider["id"] if isinstance(provider, dict) else ""
            if provider_id.lower() == "github":
                repo_name = repo["name"]
                source_version = def_ref["sourceVersion"]["id"]
                if repo_name and source_version:
                    commit_url = f"https://github.com/{repo_name}/commit/{source_version}"
                    break

        result.append({
            "releaseId": item["release"]["id"],
            "pipelineName": item["releaseDefinition"]["name"],
            "releaseName": item["release"]["name"],
            "environment": item["releaseEnvironment"]["name"],
            "status": item["deploymentStatus"],
            "queuedOn": item["queuedOn"],
            # "runDuration": (
            #     (lambda s, c:
            #         f"{int((parse_datetime(c) - parse_datetime(s)).total_seconds() // 60)} min "
            #         f"{int((parse_datetime(c) - parse_datetime(s)).total_seconds() % 60)} sec"
            #     )
            #     (item.get("startedOn"), item.get("completedOn"))
            #     if item.get("startedOn") and item.get("completedOn") else None
            # ),
            "pipelineUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={item['releaseDefinition']['id']}",
            "releaseUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={item['release']['id']}",
            "commitUrl": commit_url
        })
    return JSONResponse(content=result)


@router.get("/api/iteration-work-items",
    description="Fetches detailed work item info for a given iteration and project",
    response_description="Detailed work item info for the iteration",
    responses={
        200: {
            "description": "Detailed work item info for the iteration",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 2385768,
                            "areaPath": "Administrative Technology\\Human Resources\\Caregiver Health\\Caregiver Health Platform\\CHP - Engineering",
                            "iterationPath": "Administrative Technology\\Human Resources\\Caregiver Health Platform\\Feature Team Stingray\\Sprint 13 - Mini",
                            "assignedTo": "Jane Doe",
                            "title": "Fix login bug",
                            "state": "Closed",
                            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/2385768"
                        },
                        {
                            "id": 2385544,
                            "areaPath": "Administrative Technology\\Human Resources\\Caregiver Health\\Caregiver Health Platform\\CHP - Engineering",
                            "iterationPath": "Administrative Technology\\Human Resources\\Caregiver Health Platform\\Feature Team Stingray\\Sprint 13 - Mini",
                            "assignedTo": "John Smith",
                            "title": "Add new dashboard",
                            "state": "Active",
                            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/2385544"
                        }
                    ]
                }
            }
        }
    }
)
async def get_iteration_work_items(
    iteration_id: str = Query(..., description="Iteration ID"),
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    work_item_relations, error = fetch_iteration_work_items(iteration_id, project)
    if error:
        raise HTTPException(status_code=500, detail=error)

    unique_ids = set()
    for rel in work_item_relations:
        if rel.get("source") and rel["source"].get("id"):
            unique_ids.add(str(rel["source"]["id"]))
        if rel.get("target") and rel["target"].get("id"):
            unique_ids.add(str(rel["target"]["id"]))

    if not unique_ids:
        return JSONResponse(content=[])

    work_items, error = fetch_work_items(list(unique_ids), project)
    if error:
        raise HTTPException(status_code=500, detail=error)

    results = []
    for data in work_items:
        fields = data.get("fields", {})
        assigned_to = fields.get("System.AssignedTo", {})
        if isinstance(assigned_to, dict):
            assigned_to_name = assigned_to.get("displayName")
        else:
            assigned_to_name = assigned_to

        result = {
            "id": data.get("id"),
            "areaPath": fields.get("System.AreaPath"),
            "iterationPath": fields.get("System.IterationPath"),
            "assignedTo": assigned_to_name,
            "title": fields.get("System.Title"),
            "state": fields.get("System.State"),
            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/{}".format(data.get("id"))
        }
        results.append(result)
    return JSONResponse(content=results)


@router.post("/api/create-project",
    description="Create a new project and urls.json",
    responses={
        200: {
            "description": "Project created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Project 'MyNewProject' created."
                    }
                }
            }
        }
    }
)
async def create_project(
    req: ProjectCreateRequest
    ):
    project_name = req.project_name.strip()
    release_links = req.releases
    tags = getattr(req, "tags", [])
    team_name = req.teamName.strip()
    path = req.path.strip()

    if not project_name or not team_name or not path:
        raise HTTPException(status_code=400, detail="Project name, team name, and path are required.")

    try:
        create_project_directory(project_name, release_links, tags)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project directory or urls.json: {e}")

    try:
        append_project_to_projects_json(project_name, path, team_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update projects.json: {e}")

    return JSONResponse(content={"success": True, "message": f"Project '{project_name}' created."})


@router.get("/api/project-info",
    description="Get urls.json and project metadata for a project (project_name as query parameter)",
    responses={
        200: {
            "description": "urls.json and project metadata",
            "content": {
                "application/json": {
                    "example": {
                        "urls": {
                            "all-releases": "...",
                            "single-release": "...",
                            "release-workItems": "...",
                            "iterations-list": "...",
                            "wiql-url": "...",
                            "iteration-work-items": "...",
                            "work-items": "...",
                            "wiki-pages": "...",
                            "releases": [
                                "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=281",
                                "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=282"
                            ],
                            "tags": ["OnboardMe", "Release Plan"]
                        },
                        "project": {
                            "projectName": "CHMP",
                            "path": "CHMP",
                            "teamName": "CHS Hub - Raptor"
                        }
                    }
                }
            }
        }
    }
)
async def get_project_info(
    project_name: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    urls_path = os.path.join(base_dir, project_name, 'urls.json')
    projects_json_path = os.path.join(base_dir, 'projects.json'),
    

    try:
        with open(urls_path, 'r') as f:
            urls_data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"urls.json for project '{project_name}' not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading urls.json: {e}")

    try:
        with open(projects_json_path, 'r') as f:
            projects = json.load(f)
        project_meta = next((p for p in projects if p['projectName'] == project_name), None)
        if not project_meta:
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in projects.json.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading projects.json: {e}")

    releases_links = []
    if "definition-ids" in urls_data:
        releases_links = [
            f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={id}"
            for id in urls_data["definition-ids"]
        ]
    urls_data["releases"] = releases_links

    return JSONResponse(content={
        "urls": urls_data,
        "project": project_meta
    })


@router.get(
    "/api/release-work-items",
    description="Fetches work item details attached to a release",
    response_description="List of work item details for the release",
    responses={
        200: {
            "description": "List of work item details for the release",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "title": "Fix login bug",
                            "state": "Closed",
                            "reason": "Completed",
                            "assignedTo": "Jane Doe",
                            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/238567"
                        },
                        {
                            "title": "Add new dashboard",
                            "state": "Active",
                            "reason": "Work started",
                            "assignedTo": "John Smith",
                            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/2385644"
                        }
                    ]
                }
            }
        }
    }
)
async def get_release_work_items(
    release_id: int = Query(..., description="Release ID"),
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    work_items, error = fetch_release_work_items(release_id, project)
    if error:
        raise HTTPException(status_code=500, detail=error)
    return JSONResponse(content=work_items)


@router.get(
    "/api/deployed-environments",
    description="Fetches environments for a release definition and returns environment name and release progress URL",
    response_description="List of environments with their current release progress URLs",
    responses={
        200: {
            "description": "List of environments with release progress URLs",
            "content": {
                "application/json": {
                    "example": {
                        "environments": [
                            {
                                "environmentName": "Dev",
                                "releaseId": 45268,
                                "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12345"
                            }
                        ],
                        "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=285"
                    }
                }
            }
        }
    }
)
async def get_deployed_environments(
    project: str = Query(..., description="Project name, e.g., 'CHMP'"),
    definitionId: int = Query(..., description="Release definition ID")
):
    data, error = fetch_release_definition(project, definitionId)
    if error:
        raise HTTPException(status_code=500, detail=error)

    environments = data.get("environments", [])
    result = []
    for env in environments:
        env_name = env.get("name")
        current_release = env.get("currentRelease")
        if env_name and current_release and current_release.get("id"):
            release_id = current_release["id"]
            release_progress_url = f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={release_id}"
            result.append({
                "environmentName": env_name,
                "releaseId": release_id,
                "releaseUrl": release_progress_url
            })
            
    pipeline_url = f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={definitionId}"
    return JSONResponse(content={
        "environments": result,
        "pipelineUrl": pipeline_url
    })


@router.get(
    "/api/pending-approvals",
    description="Returns pending approvals with pipeline, environment, approver, and createdOn info for a project and date range",
    response_description="List of pending approvals with pipeline and environment details",
    responses={
        200: {
            "description": "List of pending approvals summary",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "pipelineName": "AT_MAP_BusinessProcess_SVC_CD",
                            "environmentName": "PR to Archive Branch",
                            "approver": "[TEAM FOUNDATION]\\AT-CHMP Service Engineering",
                            "createdOn": "2025-06-29T04:40:48.623Z",
                            "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=285",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=43354"
                        }
                    ]
                }
            }
        }
    }
)
async def get_pending_approvals_summary(
    startDate: str = Query(..., description="Start date"),
    endDate: str = Query(..., description="End date"),
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    # Fetch pending approvals using the utility function
    approvals, error = fetch_pending_approvals_from_pipelines(startDate, endDate, project)
    if error:
        raise HTTPException(status_code=500, detail=error)

    # Fetch pipeline releases to map releaseId to pipelineUrl/releaseUrl
    releases, rel_error = fetch_pipeline_releases(startDate, endDate, project)
    release_lookup = {}
    if not rel_error:
        for rel in releases:
            release_lookup[str(rel["id"])] = {
                "definitionId": rel["releaseDefinition"]["id"],
                "pipelineUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={rel['releaseDefinition']['id']}",
                "releaseUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={rel['id']}"
            }

    results = []
    for item in approvals:
        pipeline_name = item.get("releaseDefinition", {}).get("name")
        environment_name = item.get("releaseEnvironment", {}).get("name")
        approver = item.get("approver", {}).get("displayName")
        created_on = item.get("createdOn")
        definition_id = item.get("releaseDefinition", {}).get("id")
        release_id = str(item.get("release", {}).get("id"))
        pipeline_url = release_url = None
        if release_id in release_lookup:
            pipeline_url = release_lookup[release_id]["pipelineUrl"]
            release_url = release_lookup[release_id]["releaseUrl"]
        else:
            pipeline_url = f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={definition_id}"
            release_url = f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={release_id}"

        results.append({
            "pipelineName": pipeline_name,
            "environmentName": environment_name,
            "approver": approver,
            "createdOn": created_on,
            "pipelineUrl": pipeline_url,
            "releaseUrl": release_url
        })
    return JSONResponse(content=results)


@router.get(
    "/api/release-plan-work-items",
    description="Fetches work items from the release plan using tags and WIQL API as defined in urls.json for the project, and returns their title and web URL",
    response_description="List of work item titles and URLs matching the tags in urls.json",
    responses={
        200: {
            "description": "List of work item titles and URLs matching the tags",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "title": "Release: Sprint 13",
                            "webUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/12345"
                        }
                    ]
                }
            }
        }
    }
)
async def get_release_plan_work_items(
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    import requests

    work_item_objs, error = fetch_release_plan(project)
    if error:
        raise HTTPException(status_code=500, detail=error)
    results = []
    for item in work_item_objs:
        url = item.get("url")
        if not url:
            continue
        data, error = fetch_azure_url(url)
        if error:
            raise HTTPException(status_code=500, detail=error)
        title = data.get("fields", {}).get("System.IterationPath")
        web_url = data.get("_links", {}).get("html", {}).get("href")
        if title and web_url:
            results.append({
                "title": title,
                "webUrl": web_url
            })
    return JSONResponse(content=results)

@router.get(
    "/api/test-plan-result",
    description="Returns the sum of all test-related fields for a given project and sprint, with detailed outcome breakdown for unanalyzed tests",
    response_description="Aggregated test run summary for the test plan",
    responses={
        200: {
            "description": "Aggregated test run summary",
            "content": {
                "application/json": {
                    "example": {
                        "totalTests": 10,
                        "incompleteTests": 2,
                        "notApplicableTests": 1,
                        "passedTests": 7,
                        "failedTests": 0,
                        "blockedTests": 1,
                        "url": "https://dev.azure.com/PSJH/Administrative%20Technology/_testPlans/execute?planId=123456",
                        "success": True
                    }
                }
            }
        }
    }
)
async def get_test_plan_result(
    project: str = Query(..., description="Project name, e.g., 'CHMP'"),
    sprint: str = Query(..., description="Sprint/iteration name, e.g., 'Sprint 13'")
):
    from app.utils.fetch_data import fetch_test_plan_runs, fetch_test_run_results

    runs_json, error = fetch_test_plan_runs(project, sprint)
    if error:
        raise HTTPException(status_code=500, detail=error)

    summary_fields = ["totalTests", "incompleteTests", "notApplicableTests", "passedTests", "unanalyzedTests"]
    summary = {field: 0 for field in summary_fields}
    run_ids_with_unanalyzed = []

    for run in runs_json.get("value", []):
        for field in summary_fields:
            summary[field] += run.get(field, 0)
        if run.get("unanalyzedTests", 0) > 0:
            run_ids_with_unanalyzed.append(run.get("id"))

    outcome_counts = {}
    if summary["unanalyzedTests"] > 0 and run_ids_with_unanalyzed:
        from collections import Counter
        for run_id in run_ids_with_unanalyzed:
            test_results_json, err = fetch_test_run_results(project, run_id)
            if err or not test_results_json or "value" not in test_results_json:
                continue
            outcomes = [tr.get("outcome") for tr in test_results_json["value"] if tr.get("outcome")]
            for outcome, count in Counter(outcomes).items():
                if outcome in outcome_counts:
                    outcome_counts[outcome] += count
                else:
                    outcome_counts[outcome] = count

        summary.pop("unanalyzedTests", None)
        for outcome, count in outcome_counts.items():
            summary[outcome] = count
    else:
        summary["failedTests"] = summary.pop("unanalyzedTests", 0)

    if "url" in runs_json:
        summary["url"] = runs_json["url"]

    # Add success flag
    passed = summary.get("passedTests", 0)
    not_applicable = summary.get("notApplicableTests", 0)
    total = summary.get("totalTests", 0)
    summary["success"] = (passed + not_applicable) == total

    return JSONResponse(content=summary)


@router.get(
    "/api/pending-approvals-user",
    description="Fetches pending approvals assigned to a specific user for a project",
    response_description="List of pending approvals for the user with environment, pipeline, and release info",
    responses={
        200: {
            "description": "List of pending approvals for the user",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "environmentName": "Dev",
                            "pipelineName": "AT_MAP_BusinessProcess_SVC_CD",
                            "releaseName": "Release-15",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12345"
                        }
                    ]
                }
            }
        }
    }
)
async def get_pending_approvals_for_user(
    project: str = Query(..., description="Project name, e.g., 'CHMP'"),
    username: str = Query(..., description="User's email or UPN")
):
    from app.utils.fetch_data import fetch_pending_approvals_for_user

    approvals_json, error = fetch_pending_approvals_for_user(project, username)
    if error:
        raise HTTPException(status_code=500, detail=error)

    results = []
    for item in approvals_json.get("value", []):
        env_name = item.get("releaseEnvironment", {}).get("name")
        pipeline_name = item.get("releaseDefinition", {}).get("name")
        release_name = item.get("release", {}).get("name")
        release_id = item.get("release", {}).get("id")
        release_url = None
        if release_id:
            release_url = f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={release_id}"
        results.append({
            "pipelineName": pipeline_name,
            "releaseName": release_name,
            "environmentName": env_name,
            "approvalUrl": release_url
        })

    return JSONResponse(content=results)
# @router.get(
#     "/api/github-commit-url",
#     description="Fetches the GitHub commit URL for a release if the repository provider is GitHub",
#     response_description="GitHub commit URL for the release",
#     responses={
#         200: {
#             "description": "GitHub commit URL for the release",
#             "content": {
#                 "application/json": {
#                     "example": {
#                         "commitUrl": "https://github.com/PSJH/AT_MCE_CHMP/commit/debfd1e9b43735a5696cb5c478fddfcb802d0310"
#                     }
#                 }
#             }
#         }
#     }
# )
# async def get_github_commit_url(
#     release_id: int = Query(..., description="Release ID"),
#     project: str = Query(..., description="Project name, e.g., 'CHMP'")
# ):
#     commit_url, error = fetch_github_commit_url_from_release(release_id, project)
#     if error:
#         raise HTTPException(status_code=404, detail=error)
#     return JSONResponse(content={"commitUrl": commit_url})

# def parse_html_for_release_notes(item_data):
#     release_notes_html = item_data['fields'].get('Custom.ReleaseNotes', '')
#     match = re.search(r'href="(.*?)"', release_notes_html)
#     return match.group(1) if match else None
# @router.get("/api/release-plan-work-items",
#             description="Fetches data from the release plan work items",
#             response_description="data from the release plan work items(only last 10 releases)"
# )
# async def get_release_plan_work_items(
#     project: str = Query(..., description="Project name, e.g., 'CHMP'")
# ):
#     release_plan_work_items, error = fetch_wiql_url(project)
#     if error:
#         raise HTTPException(status_code=500, detail=error)

#     release_plan_work_items = release_plan_work_items[-10:]
#     results = []
#     for item in release_plan_work_items:
#         item_data, detail_error = fetch_release_plan_work_items(item["url"])
#         if detail_error:
#             continue
#         results.append({
#             "id": item_data["id"],
#             "title": item_data["fields"].get("System.Title"),
#             "state": item_data["fields"].get("System.State"),
#             "webUrl": item_data["_links"]["html"]["href"],
#             "githubPRs": item_data["_links"]["workItemUpdates"]["href"],
#             "release_notes_html": parse_html_for_release_notes(item_data),
#             "PM Approval to Production": item_data['fields'].get('Custom.PMApprovaltoProduction'),
#             "Dev Approval to Staging": item_data['fields'].get('Custom.DevApprovaltoStaging'),
#             "SE Approval to Production": item_data['fields'].get('Custom.SEApprovaltoProduction'),
#             "Approval to Staging": item_data['fields'].get('Custom.ApprovaltoStaging'),
#         })
#     return JSONResponse(content=results)