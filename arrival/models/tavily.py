"""Tavily Search API client for web research (appliance manuals, clearances, safety guidelines).

Supports standard TAVILY_API_KEY from environment or local .env.
Falls back to TavilyNotConfigured when no API key is available.
"""

from __future__ import annotations

import json
import urllib.request

from arrival import config as settings
from arrival.config import load_dotenv  # noqa: F401  (kept importable from here)

DEFAULT_BASE_URL = "https://api.tavily.com/search"


class TavilyNotConfigured(RuntimeError):
    pass


def config() -> dict:
    return {
        "api_key": settings.get("TAVILY_API_KEY"),
        "base_url": settings.get("TAVILY_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
    }


def search(query: str, search_depth: str = "basic", include_answer: bool = True,
           max_results: int = 5, timeout: float = 30.0) -> dict:
    """Execute a web search using the Tavily Search API.

    Returns the parsed JSON dictionary from Tavily containing 'query', 'answer',
    and list of 'results'.
    """
    cfg = config()
    if not cfg["api_key"]:
        raise TavilyNotConfigured("TAVILY_API_KEY is not set in environment or .env")

    payload = {
        "api_key": cfg["api_key"],
        "query": query,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "max_results": max_results,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"],
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)
