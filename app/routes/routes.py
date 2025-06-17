from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from app.utils.fetch_data import fetch_iterations, fetch_releases

router = APIRouter()

@router.get("/api/releases")
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

@router.get("/api/pipelines")
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