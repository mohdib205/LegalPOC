"""
Thin client for the Indian Kanoon API.

 API token at https://api.indiankanoon.org/ (Rs 500 free credit to start).

Set your token before running anything:
    Windows (PowerShell):  $env:INDIANKANOON_API_TOKEN="your_token_here"
    Mac/Linux:             export INDIANKANOON_API_TOKEN="your_token_here"

IMPORTANT: run this file directly first (see bottom) to print a real raw
response and confirm field names match what fetch_judgments.py assumes.
"""
from dotenv import load_dotenv
import os
import time
import requests
load_dotenv()

BASE_URL = "https://api.indiankanoon.org"


def _get_token():
    token = os.environ.get("INDIANKANOON_API_TOKEN")
    if not token:
        raise RuntimeError(
            "INDIANKANOON_API_TOKEN not set. Sign up at https://api.indiankanoon.org/ first."
        )
    return token


def _headers():
    return {"Authorization": f"Token {_get_token()}"}


def search(query: str, pagenum: int = 0, doctypes: str = None,
           fromdate: str = None, todate: str = None):
    params = {"formInput": query, "pagenum": pagenum}
    if doctypes:
        params["doctypes"] = doctypes
    if fromdate:
        params["fromdate"] = fromdate
    if todate:
        params["todate"] = todate

    resp = requests.post(f"{BASE_URL}/search/", headers=_headers(), params=params, timeout=30)
    if not resp.ok:
        print(f"API Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()




def fetch_document(doc_id):
    resp = requests.post(f"{BASE_URL}/doc/{doc_id}/", headers=_headers(), timeout=30)
    if not resp.ok:
        print(f"API Error {resp.status_code}: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def search_and_collect(query: str, max_results: int = 40, doctypes: str = None,
                        fromdate: str = None, todate: str = None, sleep_secs: float = 1.0):
    collected = []
    page = 0
    dropped_count = 0
    while len(collected) < max_results:
        data = search(query, pagenum=page, doctypes=doctypes, fromdate=fromdate, todate=todate)
        docs = data.get("docs", [])
        if not docs:
            break
            
        for doc in docs:
            if doctypes == "delhidc":
                if doc.get("docsource", "").strip() != "Delhi District Court":
                    dropped_count += 1
                    continue
            collected.append(doc)
            if len(collected) >= max_results:
                break
                
        page += 1
        time.sleep(sleep_secs)
        if page > 50:
            break
            
    if doctypes == "delhidc":
        print(f"Client-side filter dropped {dropped_count} non-Delhi District Court results.")
        
    return collected[:max_results]


if __name__ == "__main__":
    print("Running a single test search call against the live Kanoon API...")
    try:
        result = search('"Section 138" "Negotiable Instruments Act"', doctypes="highcourts")
        import json
        print(json.dumps(result, indent=2)[:3000])
        print("\nCheck field names above against fetch_judgments.py's assumptions.")
    except Exception as e:
        print(f"Test call failed: {e}")
        print("Check your INDIANKANOON_API_TOKEN and remaining credit.")