"""Nebius Token Factory client (OpenAI-compatible). Unused by the demo path.
Credentials come from the environment; if TOKEN_FACTORY_API_KEY is unset, an untracked .env in the cwd or
repo root is read (only by this module, only when config() is called, never overriding set variables)."""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"  # confirm against https://docs.tokenfactory.nebius.com/

ROLES = {
    "omni": "NEMOTRON_OMNI_MODEL",          # read the scan
    "ultra": "NEMOTRON_ULTRA_MODEL",        # assemble twin, fill gaps
    "super": "NEMOTRON_SUPER_MODEL",        # propose tasks
    "lightning": "NEMOTRON_LIGHTNING_MODEL",  # wordings, labels
}


class TokenFactoryNotConfigured(RuntimeError):
    pass


def load_dotenv(paths: list[Path] | None = None) -> None:
    """Tiny stdlib .env reader: KEY=VALUE lines, '#' comments, optional quotes; existing vars win."""
    paths = paths or [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


def config() -> dict:
    if not os.environ.get("TOKEN_FACTORY_API_KEY"):
        load_dotenv()
    return {
        "api_key": os.environ.get("TOKEN_FACTORY_API_KEY"),
        "base_url": os.environ.get("TOKEN_FACTORY_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "models": {role: os.environ.get(var) for role, var in ROLES.items()},
    }


def complete(messages: list[dict], role: str = "super", model: str | None = None,
             timeout: float = 60.0, **params) -> str:
    cfg = config()
    if not cfg["api_key"]:
        raise TokenFactoryNotConfigured("TOKEN_FACTORY_API_KEY is not set. See docs/08-access.md.")
    model = model or cfg["models"].get(role)
    if not model:
        raise TokenFactoryNotConfigured(f"No model id for role {role!r}; set {ROLES.get(role, 'a model env var')}.")
    body = json.dumps({"model": model, "messages": messages, **params}).encode()
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]
