from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from app.utils.fetch_data import (
    fetch_iterations, fetch_releases,
    fetch_wiql_url, fetch_release_plan_work_items
)
import re

router = APIRouter()

def parse_html_for_release_notes(item_data):
    release_notes_html = item_data['fields'].get('Custom.ReleaseNotes', '')
    match = re.search(r'href="(.*?)"', release_notes_html)
    return match.group(1) if match else None

@router.get("/api/releases",
            description="Fetches release data for current and past iterations",
            response_description="List of releases with their details"
)
async def get_releases():
    iterations, error = fetch_iterations()
    if error:
        raise HTTPException(status_code=500, detail=error)
    release_data = [
        {
            "id": it["id"],
            "name": it["name"],
            "startDate": it["attributes"]["startDate"],
            "finishDate": it["attributes"]["finishDate"]
        }
        for it in iterations if it.get("attributes", {}).get("timeFrame") in ["current", "past"]
    ]
    return JSONResponse(content=release_data)

@router.get("/api/pipelines",
            description="Fetches pipeline data for releases within a specified date range",
            response_description="List of pipelines with their details"
)
async def get_pipeline_data(
    startDate: str = Query(..., description="Start date"),
    endDate: str = Query(..., description="End date")
                        ):
    if not startDate or not endDate:
        raise HTTPException(status_code=400, detail="Missing start or end date")
    data, error = fetch_releases(startDate, endDate)
    if error:
        raise HTTPException(status_code=500, detail=error)
    result = [
        {
            "releaseId": item["id"],
            "definitionId": item["releaseDefinition"]["id"],
            "name": item["name"],
            "status": item["status"],
            "createdOn": item["createdOn"],
            "description": item.get("description", "—"),
            "pipelineUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_release?_a=releases&view=mine&definitionId={item['releaseDefinition']['id']}",
            "releaseUrl": f"https://dev.azure.com/PSJH/Administrative%20Technology/_releaseProgress?_a=release-pipeline-progress&releaseId={item['id']}"
        }
        for item in data
    ]
    return JSONResponse(content=result)

@router.get("/api/release-plan-work-items",
            description="Fetches work items from the release plan",
            response_description="data from the release plan work items"
)
async def get_work_items():
    release_plan_work_items, error = fetch_wiql_url()
    if error:
        raise HTTPException(status_code=500, detail=error)

    results = []
    for item in release_plan_work_items:
        item_data, detail_error = fetch_release_plan_work_items(item["url"])
        if detail_error:
            continue
        results.append({
            "id": item_data["id"],
            "title": item_data["fields"].get("System.Title"),
            "state": item_data["fields"].get("System.State"),
            "webUrl": item_data["_links"]["html"]["href"],
            "githubPRs": item_data["_links"]["workItemUpdates"]["href"],
            "release_notes_html": parse_html_for_release_notes(item_data),
            "PM Approval to Production": item_data['fields'].get('Custom.PMApprovaltoProduction'),
            "Dev Approval to Staging": item_data['fields'].get('Custom.DevApprovaltoStaging'),
            "SE Approval to Production": item_data['fields'].get('Custom.SEApprovaltoProduction'),
            "Approval to Staging": item_data['fields'].get('Custom.ApprovaltoStaging'),
        })
    return JSONResponse(content=results)