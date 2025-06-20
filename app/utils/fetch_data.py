import requests
import os
import json
from dotenv import load_dotenv
import re

load_dotenv()

AZURE_PAT = os.environ.get("AZURE_PAT")
if not AZURE_PAT:
    raise Exception("AZURE_PAT environment variable not set")

AUTH = requests.auth.HTTPBasicAuth("", AZURE_PAT)
HEADERS = {
    "Accept": "application/json"
}

def get_project_info(project):
    projects_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'projects.json'
    )
    if not os.path.exists(projects_file):
        raise FileNotFoundError(f"{projects_file} not found")
    with open(projects_file, 'r') as f:
        projects = json.load(f)
    for p in projects:
        if p.get("projectName") == project:
            return p
    return None

def load_api_urls(project):
    api_json_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', project, 'urls.json'
    )
    if not os.path.exists(api_json_path):
        return None, {"error": f"No urls json file not found for project '{project}'"}
    with open(api_json_path, 'r') as f:
        api_urls = json.load(f)
    return api_urls, None

def fetch_project_names():
    """
    Fetch a list of project names from projects.json.
    """
    projects_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'data', 'projects.json'
    )
    if not os.path.exists(projects_file):
        raise FileNotFoundError(f"{projects_file} not found")
    with open(projects_file, 'r') as f:
        projects = json.load(f)
    return [p.get("projectName") for p in projects if "projectName" in p]

def fetch_releases(project):
    project_info = get_project_info(project)
    if not project_info:
        return None, {"error": f"Project '{project}' not found in projects.json"}
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    url = api_urls["iterations-list"].format(**project_info)
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch iterations"}
    return resp.json().get("value", []), None

def fetch_pipeline_releases(start, end, project):
    project_info = get_project_info(project)
    if not project_info:
        return None, {"error": f"Project '{project}' not found in projects.json"}
    params = {
        "minCreatedTime": start,
        "maxCreatedTime": end,
        "$top": 200,
        "path": f"\\{project_info['path']}",
        "api-version": "7.1"
    }
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    url = api_urls["all-releases"].format(**project_info)
    resp = requests.get(url, params=params, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch release data"}
    return resp.json().get("value", []), None

def fetch_iteration_work_items(iteration_id, project):
    project_info = get_project_info(project)
    if not project_info:
        return None, {"error": f"Project '{project}' not found in projects.json"}
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    url = api_urls["iteration-work-items"].format(iterationId=iteration_id, **project_info)
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch iteration work items"}
    return resp.json().get("workItemRelations", []), None

def fetch_work_items(work_item_ids, project="CHMP"):
    """
    Fetch details for multiple work items given a list of IDs.
    """
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    url_template = api_urls.get("work-items")
    if not url_template:
        return None, {"error": "work-items URL not found in urls.json"}
    ids_str = ",".join(str(wid) for wid in work_item_ids)
    url = url_template.format(workItemIds=f"ids={ids_str}")
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch work items {ids_str}"}
    return resp.json().get("value", []), None


# def fetch_wiql_url(project):
#     api_urls, error = load_api_urls(project)
#     if error:
#         return None, error
#     wiql_url = api_urls["wiql-url"]
#     resp = requests.get(wiql_url, auth=AUTH, headers=HEADERS)
#     if resp.status_code != 200:
#         return None, {"error": "Failed to fetch WIQL work items"}
#     work_items = resp.json().get("workItems", [])
#     return work_items, None

# def fetch_release_plan_work_items(url):
#     resp = requests.get(url, auth=AUTH, headers=HEADERS)
#     if resp.status_code != 200:
#         return None, {"error": f"Failed to fetch work item detail for {url}"}
#     return resp.json(), None