"""Nebius Token Factory client (OpenAI-compatible). Unused by the demo path.
Credentials come from arrival.config: the environment, else an untracked .env in the cwd or repo root (read only
when a value is unset, never overriding set variables)."""

from __future__ import annotations

import json
import urllib.request

from arrival import config as settings
from arrival.config import load_dotenv  # noqa: F401  (kept importable from here)

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"  # confirm against https://docs.tokenfactory.nebius.com/

ROLES = {
    "omni": "NEMOTRON_OMNI_MODEL",          # read the scan
    "ultra": "NEMOTRON_ULTRA_MODEL",        # assemble twin, fill gaps
    "super": "NEMOTRON_SUPER_MODEL",        # propose tasks
    "lightning": "NEMOTRON_LIGHTNING_MODEL",  # wordings, labels
}


class TokenFactoryNotConfigured(RuntimeError):
    pass


def config() -> dict:
    return {
        "api_key": settings.get("TOKEN_FACTORY_API_KEY"),
        "base_url": settings.get("TOKEN_FACTORY_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "models": {role: settings.get(var) for role, var in ROLES.items()},
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
