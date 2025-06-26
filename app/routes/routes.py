from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import os
import json
import re
import urllib.parse
from app.utils.fetch_data import (
    fetch_pipeline_releases, fetch_iterations,
    # fetch_wiql_url, fetch_release_plan_work_items
    fetch_iteration_work_items, fetch_work_items,
    fetch_project_names, fetch_pipeline_releases_by_definition,
    fetch_wiki_pages, fetch_release_work_items
)
from app.utils.form_utils import (
    ProjectCreateRequest,
    create_project_directory_and_urls,
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


@router.get("/api/pipelines-by-definition",
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
                            "name": "CHMP - UI Release",
                            "path": "\\CHMP\\UI",
                            "status": "active",
                            "createdOn": "2024-06-01T12:00:00Z",
                            "description": "Release for UI changes",
                            "pipelineUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId=679",
                            "releaseUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId=12345"
                        },
                        {
                            "releaseId": 12346,
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
async def get_pipeline_data_by_definition(
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
    result = [
        {
            "releaseId": item["id"],
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
async def create_project(req: ProjectCreateRequest):
    project_name = req.project_name.strip()
    pipelines = req.pipelines
    releases = req.releases
    team_name = req.teamName.strip()
    path = req.path.strip()

    if not project_name or not team_name or not path:
        raise HTTPException(status_code=400, detail="Project name, team name, and path are required.")

    try:
        create_project_directory_and_urls(project_name, pipelines, releases)
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
                            "all-releases": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/releases",
                            "single-release": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/releases/{releaseId}?api-version=7.2-preview.9",
                            "release-workItems": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/build/builds/{buildId}/workitems?api-version=7.2-preview.2",
                            "iterations-list": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations?&api-version=7.1",
                            "wiql-url": "https://dev.azure.com/PSJH/1b24dd3b-420d-469b-a3d3-b3e04acc5cc0/_apis/wit/wiql/f15729e0-53bd-4525-b9cb-3f3db9af8bff?api-version=7.1",
                            "iteration-work-items": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations/{iterationId}/workitems?api-version=7.2-preview.1",
                            "work-items": " https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wit/workitems?{workItemIds}&api-version=7.2-preview.3",
                            "wiki-pages": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wiki/wikis/Administrative-Technologies.wiki/pages?path=Applications/HR and Onboarding/Caregiver Health Services/Release Notes&recursionLevel=OneLevel&api-version=7.1"
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
async def get_project_info(project_name: str = Query(..., description="Project name, e.g., 'CHMP'")):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    urls_path = os.path.join(base_dir, project_name, 'urls.json')
    projects_json_path = os.path.join(base_dir, 'projects.json')

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
                            "assignedTo": "Jane Doe"
                        },
                        {
                            "title": "Add new dashboard",
                            "state": "Active",
                            "reason": "Work started",
                            "assignedTo": "John Smith"
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