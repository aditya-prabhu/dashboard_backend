from pydantic import BaseModel
from typing import List
import os
import json
import re

DEFAULT_URLS = {
    "all-releases": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/releases",
    "single-release": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/releases/{releaseId}?api-version=7.2-preview.9",
    "release-workItems": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/build/builds/{buildId}/workitems?api-version=7.2-preview.2",
    "release-definition": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/definitions/{definitionId}?api-version=7.1",
    "pipeline-runs": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/deployments",
    "pending-approvals": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/approvals?statusFilter=pending&releaseIdsFilter={releaseIds}&api-version=7.2-preview.3",
    "iterations-list": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations?&api-version=7.1",
    "iteration-work-items": "https://dev.azure.com/PSJH/Administrative%20Technology/{teamName}/_apis/work/teamsettings/iterations/{iterationId}/workitems?api-version=7.2-preview.1",
    "work-items": " https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wit/workitems?{workItemIds}&api-version=7.2-preview.3",
    "wiki-pages": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wiki/wikis/Administrative-Technologies.wiki/pages?path=Applications/HR and Onboarding/Caregiver Health Services/Release Notes&recursionLevel=OneLevel&api-version=7.1",
    "wiql-url": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/wit/wiql?api-version=7.1-preview.2",
    "list-testplans": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/testplan/plans?continuationToken=0&filterActivePlans=true&api-version=7.2-preview.1",
    "testplan-url": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/test/runs?planId={planId}&api-version=7.1",
    "testrun-result": "https://dev.azure.com/PSJH/Administrative%20Technology/_apis/test/Runs/{runId}/results?api-version=7.1",
    "user-pending-approvals": "https://vsrm.dev.azure.com/PSJH/Administrative%20Technology/_apis/release/approvals?assignedToFilter={userName}&api-version=7.2-preview.3",
}

class ProjectCreateRequest(BaseModel):
    project_name: str
    releases: List[str] = []
    teamName: str
    path: str
    tags: List[str] = []

def create_project_directory(project_name, release_links, tags):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', project_name)
    os.makedirs(base_dir, exist_ok=True)
    urls_json_path = os.path.join(base_dir, 'urls.json')

    urls_data = DEFAULT_URLS.copy()

    definition_ids = []
    pattern = re.compile(r'definitionId=(\d+)')
    for link in release_links:
        match = pattern.search(link)
        if match:
            definition_ids.append(int(match.group(1)))
            
    urls_data["definition-ids"] = list(sorted(set(definition_ids)))
    urls_data["tags"] = tags

    with open(urls_json_path, 'w') as f:
        json.dump(urls_data, f, indent=4)

def append_project_to_projects_json(project_name, path, team_name):
    projects_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'projects.json')
    if os.path.exists(projects_json_path):
        with open(projects_json_path, 'r') as f:
            projects = json.load(f)
    else:
        projects = []

    if not any(p['projectName'] == project_name for p in projects):
        projects.append({
            "projectName": project_name,
            "path": path,
            "teamName": team_name
        })
        with open(projects_json_path, 'w') as f:
            json.dump(projects, f, indent=4)