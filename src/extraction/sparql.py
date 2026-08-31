"""Minimal client for the Wikidata SPARQL endpoint (WDQS) and Wikimedia APIs.

WDQS etiquette: send a descriptive User-Agent and back off on HTTP 429.
"""

import time

import requests

from config import USER_AGENT, WIKIDATA_SPARQL

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


def sparql_select(query: str, retries: int = 4) -> list[dict]:
    """Run a SELECT query on WDQS and return rows as {variable: value} dicts."""
    headers = {"Accept": "application/sparql-results+json"}
    for attempt in range(1, retries + 1):
        resp = _session.get(
            WIKIDATA_SPARQL, params={"query": query}, headers=headers, timeout=120
        )
        if resp.status_code in (429, 502, 503) and attempt < retries:
            time.sleep(int(resp.headers.get("Retry-After", 5)) * attempt)
            continue
        resp.raise_for_status()
        bindings = resp.json()["results"]["bindings"]
        return [{var: cell["value"] for var, cell in row.items()} for row in bindings]
    raise RuntimeError("WDQS kept rejecting the query, try again later")


def api_get(url: str, params: dict, retries: int = 4) -> dict:
    """GET a Wikimedia Action API endpoint and return the parsed JSON."""
    for attempt in range(1, retries + 1):
        resp = _session.get(url, params={**params, "format": "json"}, timeout=60)
        if resp.status_code == 429 and attempt < retries:
            time.sleep(int(resp.headers.get("Retry-After", 10)) * attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"{url} kept rate-limiting, try again later")


def qid(uri: str) -> str:
    """'http://www.wikidata.org/entity/Q296' -> 'Q296'."""
    return uri.rsplit("/", 1)[-1]


def chunked(items: list, size: int):
    """Yield successive chunks of `items` (WDQS queries stay small and fast)."""
    for i in range(0, len(items), size):
        yield items[i : i + size]
