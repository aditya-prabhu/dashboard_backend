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

api_json_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'CHMP', 'api.json'
)
with open(api_json_path, 'r') as f:
    api_urls = json.load(f)

def fetch_releases():
    resp = requests.get(api_urls["iterations-list"], auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch iterations"}
    return resp.json().get("value", []), None

def fetch_pipeline_releases(start, end):
    params = {
        "minCreatedTime": start,
        "maxCreatedTime": end,
        "$top": 200,
        "path": "\\CHMP",
        "api-version": "7.1"
    }
    resp = requests.get(api_urls["all-releases"], params=params, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch release data"}
    return resp.json().get("value", []), None

def fetch_wiql_url():
    wiql_url = api_urls["wiql-url"]
    resp = requests.get(wiql_url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": "Failed to fetch WIQL work items"}
    work_items = resp.json().get("workItems", [])
    return work_items, None

def fetch_release_plan_work_items(url):
    resp = requests.get(url, auth=AUTH, headers=HEADERS)
    if resp.status_code != 200:
        return None, {"error": f"Failed to fetch work item detail for {url}"}
    return resp.json(), None