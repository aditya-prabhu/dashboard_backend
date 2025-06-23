from pydantic import BaseModel
from typing import List
import os
import json

DEFAULT_URLS = {
    "all-releases": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/releases",
    "iterations-list": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations?&api-version=7.1",
    "wiql-url": "https://dev.azure.com/PSJH/1b24dd3b-420d-469b-a3d3-b3e04acc5cc0/_apis/wit/wiql/f15729e0-53bd-4525-b9cb-3f3db9af8bff?api-version=7.1",
    "iteration-work-items": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations/{iterationId}/workitems?api-version=7.2-preview.1",
    "work-items": " https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wit/workitems?{workItemIds}&api-version=7.2-preview.3"
}

class ProjectCreateRequest(BaseModel):
    project_name: str
    pipelines: List[str] = []
    releases: List[str] = []
    teamName: str
    path: str

def create_project_directory_and_urls(project_name, pipelines, releases):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', project_name)
    os.makedirs(base_dir, exist_ok=True)
    urls_json_path = os.path.join(base_dir, 'urls.json')

    urls_data = DEFAULT_URLS.copy()
    urls_data["pipelines"] = pipelines
    urls_data["releases"] = releases

    with open(urls_json_path, 'w') as f:
        json.dump(urls_data, f, indent=4)

def append_project_to_projects_json(project_name, path, team_name):
    projects_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'projects.json')
    if os.path.exists(projects_json_path):
        with open(projects_json_path, 'r') as f:
            projects = json.load(f)
    else:
        projects = []

    # Only append if not already present
    if not any(p['projectName'] == project_name for p in projects):
        projects.append({
            "projectName": project_name,
            "path": path,
            "teamName": team_name
        })
        with open(projects_json_path, 'w') as f:
            json.dump(projects, f, indent=4)