from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
import os
import json
import re
from app.utils.fetch_data import (
    fetch_pipeline_releases, fetch_releases,
    # fetch_wiql_url, fetch_release_plan_work_items
    fetch_iteration_work_items, fetch_work_items,
    fetch_project_names, fetch_pipeline_releases_by_definition
)
from app.utils.form_utils import (
    ProjectCreateRequest,
    create_project_directory_and_urls,
    append_project_to_projects_json
)

router = APIRouter()

@router.get("/api/projects",
            description="Fetches the list of available projects",
            response_description="List of project names"
)
async def get_projects():
    try:
        projects = fetch_project_names()
        return JSONResponse(content=projects)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/releases",
            description="Fetches release data for current and past iterations",
            response_description="List of releases with their details"
)
async def get_releases(
    project: str = Query(..., description="Project name, e.g., 'CHMP'")
):
    iterations, error = fetch_releases(project)
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
    return JSONResponse(content=release_data)


@router.get("/api/pipelines",
            description="Fetches pipeline data for releases within a specified date range",
            response_description="List of pipelines with their details"
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

@router.get(
    "/api/pipelines-by-definition",
    description="Fetches pipeline data for a specific definitionId within a specified date range",
    response_description="List of pipelines with their details"
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
            response_description="Detailed work item info for the iteration"
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


@router.post("/api/create-project", description="Create a new project and urls.json")
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

@router.get(
    "/api/project-info",
    description="Get urls.json and project metadata for a project (project_name as query parameter)"
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