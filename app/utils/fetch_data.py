import requests
import os
import json
from dotenv import load_dotenv
import re
import httpx

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
    If 'definition-ids' is present in urls.json, fetch releases for each definitionId and append all results.
    Also fetch releases by path as before, and combine both sets (removing duplicates).

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

    api_urls, error = load_api_urls(project)
    if error:
        return None, error

    url = api_urls["all-releases"].format(**project_info)
    all_releases = []

    # 1. Fetch by definition-ids if present
    definition_ids = api_urls.get("definition-ids")
    if definition_ids and isinstance(definition_ids, list) and len(definition_ids) > 0:
        for definition_id in definition_ids:
            params = {
                "definitionId": definition_id,
                "minCreatedTime": start,
                "maxCreatedTime": end,
                "$top": 200,
                "api-version": "7.1"
            }
            resp = requests.get(url, params=params, auth=AUTH, headers=HEADERS)
            if resp.status_code == 200:
                all_releases.extend(resp.json().get("value", []))

    # 2. Fetch by path
    params = {
        "minCreatedTime": start,
        "maxCreatedTime": end,
        "$top": 200,
        "path": f"\\{project_info['path']}",
        "api-version": "7.1"
    }
    resp = requests.get(url, params=params, auth=AUTH, headers=HEADERS)
    if resp.status_code == 200:
        all_releases.extend(resp.json().get("value", []))

    return all_releases, None

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
        "minStartedTime": start,
        "maxStartedTime": end,
        "api-version": "7.1"
    }
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    url = api_urls["pipeline-runs"].format(**project_info)
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
    Given a releaseId and projectName, fetch work item details for all builds in the release.
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

    # 2. Extract all buildIds from artifacts
    build_ids = []
    for artifact in release_json.get("artifacts", []):
        def_ref = artifact.get("definitionReference", {})
        build_uri = def_ref.get("buildUri", {}).get("id", "")
        if build_uri.startswith("vstfs:///Build/Build/"):
            build_id = build_uri.split("/")[-1]
            build_ids.append(build_id)
    if not build_ids:
        return [], None

    # 3. For each buildId, call release-workItems API and collect work items
    results = []
    for build_id in build_ids:
        release_workitems_url = api_urls["release-workItems"].replace("{buildId}", str(build_id))
        workitems_resp = requests.get(release_workitems_url, auth=AUTH, headers=headers)
        if workitems_resp.status_code != 200:
            continue
        workitems_json = workitems_resp.json()
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
    
def fetch_release_definition(project_name, definition_id):
    """
    Fetch release definition details for a given project and definitionId.

    Args:
        project_name (str): The name of the project.
        definition_id (str or int): The release definition ID.

    Returns:
        tuple: (response JSON dict, error dict or None)
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    url_template = api_urls.get("release-definition")
    if not url_template:
        return None, {"error": "release-definition URL not found in urls.json"}

    url = url_template.replace("{definitionId}", str(definition_id))
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch release definition {definition_id}"}
    return resp.json(), None


def fetch_pending_approvals_from_pipelines(start, end, project):
    """
    Fetches all pending approvals for all releases in a project within a date range.

    Args:
        start (str): Start date (ISO format).
        end (str): End date (ISO format).
        project (str): The name of the project.

    Returns:
        tuple: (list of pending approvals, error dict or None)
    """
    # 1. Fetch pipeline releases
    releases, error = fetch_pipeline_releases(start, end, project)
    if error:
        return None, error

    # 2. Collect all releaseIds
    release_ids = [str(item["id"]) for item in releases if "id" in item]
    if not release_ids:
        return [], None

    # 3. Load approvals URL from urls.json
    api_urls, error = load_api_urls(project)
    if error:
        return None, error
    approvals_url_template = api_urls.get("pending-approvals")
    if not approvals_url_template:
        return None, {"error": "pending-approvals URL not found in urls.json"}

    # 4. Prepare approvals URL
    release_ids_str = ",".join(release_ids)
    approvals_url = approvals_url_template.replace("{releaseIds}", release_ids_str)

    # 5. Call the approvals API
    resp = requests.get(approvals_url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch pending approvals"}
    approvals = resp.json().get("value", [])
    return approvals, None

def fetch_release_plan(project):
    """
    Fetch work items from Azure DevOps WIQL API that have all the tags specified in /data/{project}/urls.json.

    Args:
        project (str): The project name.

    Returns:
        tuple: (list of work item IDs, error dict or None)
    """
    api_urls, error = load_api_urls(project)
    if error:
        return None, error

    wiql_url = api_urls.get("wiql-url")
    tags = api_urls.get("tags", [])
    if not wiql_url:
        return None, {"error": "wiql-url not found in urls.json"}
    if not tags:
        return None, {"error": "tags not found in urls.json"}

    tag_filters = "".join([f"\n    AND [System.Tags] CONTAINS '{tag}'" for tag in tags])
    wiql_query = f"""
        SELECT
            [System.Id],
            [System.WorkItemType],
            [System.Title],
            [System.AssignedTo],
            [System.State],
            [System.Tags]
        FROM workitems
        WHERE
            [System.TeamProject] = 'Administrative Technology'
            {tag_filters}
    """

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    resp = requests.post(
        wiql_url,
        auth=AUTH,
        headers=headers,
        json={"query": wiql_query}
    )
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch work items by tags: {resp.text}"}
    work_items = resp.json().get("workItems", [])
    #work_item_ids = [item["id"] for item in work_items]
    return work_items[-10:], None

def fetch_azure_url(url):
    """
    Fetches and returns the JSON response from a given Azure DevOps API URL.

    Args:
        url (str): The Azure DevOps API URL.

    Returns:
        tuple: (response JSON dict, error dict or None)
    """
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch data from {url}: {resp.text}"}
    return resp.json(), None

def fetch_test_plan_runs(project_name, sprint_name):
    """
    Fetch the test plan runs for a given project and sprint (iteration) name.
    Iterates through paginated results using x-ms-continuationtoken until the plan is found or all pages are exhausted.
    Once found, calls the test runs API with the planId.

    Args:
        project_name (str): The name of the project.
        sprint_name (str): The sprint/iteration name to match (should match the end of the 'iteration' field).

    Returns:
        tuple: (test runs JSON with executeUrl, error dict or None)
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    list_testplans_url = api_urls.get("list-testplans")
    test_runs_url_template = api_urls.get("testplan-url")
    if not list_testplans_url or not test_runs_url_template:
        return None, {"error": "Required test plan URLs not found in urls.json"}

    continuation_token = "0"
    headers = {
        "Accept": "application/json"
    }

    plan_id = None
    while True:
        url = re.sub(r"continuationToken=[^&]*", f"continuationToken={continuation_token}", list_testplans_url)
        resp = requests.get(url, auth=AUTH, headers=headers)
        if resp.status_code != 200:
            return None, {"error": f"Failed to fetch test plans: {resp.text}"}

        data = resp.json()
        plans = data.get("value", [])
        for plan in plans:
            iteration_path = plan.get("iteration", "")
            if iteration_path and iteration_path.split("\\")[-1].strip() == sprint_name.strip():
                plan_id = plan.get("id")
                break
        if plan_id is not None:
            break

        continuation_token = resp.headers.get("x-ms-continuationtoken")
        if not continuation_token:
            break

    if not plan_id:
        return None, {"error": f"No test plan found for sprint '{sprint_name}' in project '{project_name}'"}

    test_runs_url = test_runs_url_template.replace("{planId}", str(plan_id))
    resp = requests.get(test_runs_url, auth=AUTH, headers=headers)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch test runs for planId {plan_id}: {resp.text}"}

    result_json = resp.json()
    result_json["url"] = f"https://dev.azure.com/PSJH/Administrative%20Technology/_testPlans/execute?planId={plan_id}"

    return result_json, None

def fetch_test_run_results(project_name, run_id):
    """
    Fetch test results for a given test run in a project.

    Args:
        project_name (str): The name of the project.
        run_id (str or int): The test run ID.

    Returns:
        tuple: (test results JSON, error dict or None)
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    test_run_results_url_template = api_urls.get("testrun-result")
    if not test_run_results_url_template:
        return None, {"error": "testrun-result URL not found in urls.json"}

    url = test_run_results_url_template.replace("{runId}", str(run_id))
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch test run results for runId {run_id}: {resp.text}"}

    return resp.json(), None

def fetch_pending_approvals_for_user(project_name, username):
    """
    Fetch pending approvals assigned to a specific user for a given project.

    Args:
        project_name (str): The name of the project.
        username (str): The user's email or UPN to filter approvals.

    Returns:
        tuple: (response JSON dict, error dict or None)
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    approvals_url_template = api_urls.get("user-pending-approvals")
    if not approvals_url_template:
        return None, {"error": "pending-approvals-user URL not found in urls.json"}

    url = approvals_url_template.replace("{userName}", username)
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch pending approvals for user {username}: {resp.text}"}

    return resp.json(), None

def fetch_pipelines_by_folder_path(project_name):
    """
    Fetch pipelines for a project and filter by the pipeline-path in project_info.

    Args:
        project_name (str): The name of the project.

    Returns:
        tuple: (filtered pipelines list, error dict or None)
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    project_info = get_project_info(project_name)
    if not project_info:
        return None, {"error": f"Project '{project_name}' not found in projects.json"}

    pipelines_url = api_urls.get("yaml-pipelines-list")
    pipeline_path = project_info.get("yaml-pipelines-path").lower()
    if not pipelines_url or not pipeline_path:
        return None, {"error": "pipelines-list or pipeline-path not found in urls.json or projects.json"}

    resp = requests.get(pipelines_url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch pipelines: {resp.text}"}

    pipelines = resp.json().get("value", [])
    filtered = [
        p for p in pipelines
        if pipeline_path in (p.get("folder").lower() or "")
    ]
    return filtered, None

def fetch_builds_for_pipeline(project_name, pipeline_id, min_time, max_time):
    """
    Fetch builds for a given pipeline and time window, and also fetch in-progress builds.
    Returns merged results, removing duplicates.
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    builds_url_template = api_urls.get("yaml-pipeline-builds")
    if not builds_url_template:
        return None, {"error": "builds-url not found in urls.json"}

    # 1. Request with minTime and maxTime
    url_time = (
        builds_url_template
        .replace("{pipelineId}", str(pipeline_id))
        + f"&minTime={min_time}&maxTime={max_time}"
    )
    resp_time = requests.get(url_time, auth=AUTH, headers=HEADERS)
    if resp_time.status_code != 200:
        return None, {"error": f"Failed to fetch builds (time filter): {resp_time.text}"}
    builds_time = resp_time.json().get("value", [])

    # 2. Request with statusFilter=inProgress
    url_inprogress = (
        builds_url_template
        .replace("{pipelineId}", str(pipeline_id))
        + "&statusFilter=inProgress"
    )
    resp_inprogress = requests.get(url_inprogress, auth=AUTH, headers=HEADERS)
    if resp_inprogress.status_code != 200:
        return None, {"error": f"Failed to fetch builds (inProgress): {resp_inprogress.text}"}
    builds_inprogress = resp_inprogress.json().get("value", [])

    # 3. Merge results, removing duplicates by build id
    builds_dict = {b["id"]: b for b in builds_time}
    for b in builds_inprogress:
        builds_dict[b["id"]] = b

    merged_builds = list(builds_dict.values())
    return {"value": merged_builds}, None


async def fetch_azure_url_async(url):
    """
    Async version: Fetches and returns the JSON response from a given Azure DevOps API URL.

    Args:
        url (str): The Azure DevOps API URL.

    Returns:
        tuple: (response JSON dict, error dict or None)
    """
    AZURE_PAT = os.environ.get("AZURE_PAT")
    headers = {"Accept": "application/json"}
    auth = httpx.BasicAuth("", AZURE_PAT)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, auth=auth)
        if resp.status_code != 200:
            return None, {"error": f"Failed to fetch data from {url}: {resp.text}"}
        return resp.json(), None

async def fetch_stages_from_timeline_url(timeline_url):
    """
    Fetches the timeline and returns a list of stages (name and result), sorted by their order.
    """
    data, error = await fetch_azure_url_async(timeline_url)
    if error or not data:
        return []
    stages = [
        {
            "name": rec.get("name"),
            "result": rec.get("result"),
            "state": rec.get("state"),
            "order": rec.get("order", 0)
        }
        for rec in data.get("records", [])
        if rec.get("type", "").lower() == "stage"
    ]
    # Sort by the 'order' field
    stages_sorted = sorted(stages, key=lambda x: x["order"])
    # Remove 'order' from the returned dict if you don't want to expose it
    return [{"name": s["name"], "result": s["result"], "state": s["state"]} for s in stages_sorted]

def fetch_release_work_items_for_build(build_id, project_name):
    """
    Given a buildId and projectName, fetch work item details for that build.
    Returns a list of dicts with title, state, reason, and assignedTo.
    """
    api_urls, error = load_api_urls(project_name)
    if error:
        return None, error

    headers = {
        "Accept": "application/json"
    }

    release_workitems_url = api_urls["release-workItems"].replace("{buildId}", str(build_id))
    workitems_resp = requests.get(release_workitems_url, auth=AUTH, headers=headers)
    if workitems_resp.status_code != 200:
        return None, {"error": f"Failed to fetch work items for build {build_id}"}
    workitems_json = workitems_resp.json()
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