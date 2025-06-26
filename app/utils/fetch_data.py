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
    """
    Retrieve project information from the projects.json file for the given project name.

    Args:
        project (str): The name of the project.

    Returns:
        dict or None: Project information dictionary if found, else None.

    Raises:
        FileNotFoundError: If the projects.json file does not exist.
    """
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
    """
    Load API URLs for a given project from its urls.json file.

    Args:
        project (str): The name of the project.

    Returns:
        tuple: (api_urls dict, error dict or None)
    """
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

    Returns:
        list: List of project names.

    Raises:
        FileNotFoundError: If the projects.json file does not exist.
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

def fetch_iterations(project):
    """
    Fetch a list of iterations for a given project from Azure DevOps.

    Args:
        project (str): The name of the project.

    Returns:
        tuple: (list of iterations, error dict or None)
    """
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

def fetch_wiki_pages(project):
    """
    Fetch wiki pages from Azure DevOps for a given project.

    Args:
        project (str): The name of the project.

    Returns:
        tuple: (wiki pages JSON, error dict or None)
    """
    project_info = get_project_info(project)
    if not project_info:
        return None, {"error": f"Project '{project}' not found in projects.json"}
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    wiki_url = api_urls.get("wiki-pages")
    if not wiki_url:
        return None, {"error": "wiki-pages URL not found in urls.json"}
    resp = requests.get(wiki_url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch wiki pages"}
    return resp.json(), None

def fetch_pipeline_releases(start, end, project):
    """
    Fetch pipeline releases for a project within a date range.

    Args:
        start (str): Start date (ISO format).
        end (str): End date (ISO format).
        project (str): The name of the project.

    Returns:
        tuple: (list of releases, error dict or None)
    """
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

def fetch_pipeline_releases_by_definition(start, end, project, definition_id):
    """
    Fetch pipeline releases for a specific definitionId(pipeline) within a date range.

    Args:
        start (str): Start date (ISO format).
        end (str): End date (ISO format).
        project (str): The name of the project.
        definition_id (str or int): The pipeline definition ID.

    Returns:
        tuple: (list of releases, error dict or None)
    """
    project_info = get_project_info(project)
    if not project_info:
        return None, {"error": f"Project '{project}' not found in projects.json"}
    params = {
        "definitionId": definition_id,
        "minCreatedTime": start,
        "maxCreatedTime": end,
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
    """
    Fetch work items for a specific iteration in a project.

    Args:
        iteration_id (str): The iteration ID.
        project (str): The name of the project.

    Returns:
        tuple: (list of work item relations, error dict or None)
    """
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

    Args:
        work_item_ids (list): List of work item IDs.
        project (str, optional): The name of the project. Defaults to "CHMP".

    Returns:
        tuple: (list of work item details, error dict or None)
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

def fetch_release_work_items(release_id, project_name):
    """
    Given a releaseId and projectName, fetch work item details for the release.
    Returns a list of dicts with title, state, reason, and assignedTo.
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    headers = {
        "Accept": "application/json"
    }

    # 1. Call single-release API
    single_release_url = api_urls["single-release"].replace("{releaseId}", str(release_id))
    resp = requests.get(single_release_url, auth=AUTH, headers=headers)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch release {release_id}"}
    release_json = resp.json()

    # 2. Extract buildId from artifacts
    build_id = None
    for artifact in release_json.get("artifacts", []):
        def_ref = artifact.get("definitionReference", {})
        build_uri = def_ref.get("buildUri", {}).get("id", "")
        # Extract the build number from "vstfs:///Build/Build/716812"
        if build_uri.startswith("vstfs:///Build/Build/"):
            build_id = build_uri.split("/")[-1]
            break
    if not build_id:
        return None, {"error": "Build ID not found in release artifacts."}

    # 3. Call release-workItems API
    release_workitems_url = api_urls["release-workItems"].replace("{buildId}", str(build_id))
    workitems_resp = requests.get(release_workitems_url, auth=AUTH, headers=headers)
    if workitems_resp.status_code != 200:
        return None, {"error": f"Failed to fetch work items for build {build_id}"}
    workitems_json = workitems_resp.json()

    # 4. For each work item, fetch details
    results = []
    for item in workitems_json.get("value", []):
        wi_url = item["url"]
        wi_resp = requests.get(wi_url, auth=AUTH, headers=headers)
        if wi_resp.status_code != 200:
            continue
        wi_json = wi_resp.json()
        fields = wi_json.get("fields", {})
        results.append({
            "title": fields.get("System.Title"),
            "state": fields.get("System.State"),
            "reason": fields.get("System.Reason"),
            "assignedTo": (
                fields.get("System.AssignedTo", {}).get("displayName")
                if isinstance(fields.get("System.AssignedTo"), dict)
                else fields.get("System.AssignedTo")
            ),
            "htmlUrl": "https://dev.azure.com/PSJH/Administrative%20Technology/_workitems/edit/{}".format(item["id"])

        })
    return results, None

# Example usage:
# pat = "<base64 encoded PAT or use requests.auth.HTTPBasicAuth if preferred>"
# print(get_release_work_items(123456, "CHMP", pat))

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