"""Tavily Search API client for web research (appliance manuals, clearances, safety guidelines).

Supports standard TAVILY_API_KEY from environment or local .env.
Falls back to TavilyNotConfigured when no API key is available.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.tavily.com/search"


class TavilyNotConfigured(RuntimeError):
    pass


def load_dotenv(paths: list[Path] | None = None) -> None:
    """Tiny stdlib .env reader: KEY=VALUE lines, '#' comments, optional quotes; existing vars win."""
    paths = paths or [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def config() -> dict:
    if not os.environ.get("TAVILY_API_KEY"):
        load_dotenv()
    return {
        "api_key": os.environ.get("TAVILY_API_KEY"),
        "base_url": os.environ.get("TAVILY_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
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
