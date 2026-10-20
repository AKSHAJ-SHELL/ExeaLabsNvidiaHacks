"""Tavily AI Research Agent for kitchen appliances, physical clearances, and robot safety constraints.

Uses the Tavily Search API to gather real-world appliance manuals, hinge mechanisms,
and operating guidelines, enriching the digital twin and informing Nemotron VLM planning.
Maintains an offline cache in arrival/models/tavily_cache.json for network-free execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arrival.models.tavily import TavilyNotConfigured, search as tavily_search

DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "models" / "tavily_cache.json"

APPLIANCE_QUERIES = {
    "dishwasher": "residential kitchen dishwasher door latch mechanism and safe loading clearance",
    "stove": "residential gas range cooktop burner safety and knob operation",
    "gas_range": "residential gas range cooktop burner safety and knob operation",
    "fridge": "residential refrigerator bottom freezer door handle and seal pull force",
    "fridge_bottom_freezer": "residential refrigerator bottom freezer door handle and seal pull force",
    "microwave": "residential kitchen microwave door push button and handle release",
    "sink": "kitchen sink faucet lever mixing valve operation and splash containment",
}

FALLBACK_KNOWLEDGE = {
    "dishwasher": {
        "summary": "Dishwasher door features downward swinging counterbalanced hinge with top release latch.",
        "safety_guidelines": [
            "Ensure arm clears lower rack edge when door is in horizontal open position.",
            "Verify cycle completion before attempting unlatch.",
        ],
        "operating_steps": [
            "Grasp upper recess handle.",
            "Pull horizontally outward to disengage latch.",
            "Guide door downward 90 degrees to rest flat.",
        ],
    },
    "stove": {
        "summary": "Gas range features manual burner knobs and heavy iron grates over burners.",
        "safety_guidelines": [
            "Maintain 15 cm arm clearance from active burners.",
            "Do not wipe or rest end-effector on grates until surface cools.",
        ],
        "operating_steps": [
            "Push knob inward and rotate counter-clockwise to ignite.",
            "Return knob clockwise to OFF position when finished.",
        ],
    },
    "fridge": {
        "summary": "Refrigerator utilizes magnetic gasket requiring 15-20N breakaway force.",
        "safety_guidelines": [
            "Allow swing clearance along vertical hinge axis.",
            "Avoid rapid door snapping to preserve seal integrity.",
        ],
        "operating_steps": [
            "Grasp vertical bar handle firmly.",
            "Apply outward pull perpendicular to cabinet face.",
            "Swing door open to 90 degrees detent.",
        ],
    },
    "microwave": {
        "summary": "Microwave door utilizes side handle or button with instant safety interlocks.",
        "safety_guidelines": [
            "Never place metallic or reflective objects into the microwave cavity.",
            "Verify door is fully closed before start command.",
        ],
        "operating_steps": [
            "Press release button or pull door handle horizontally.",
            "Swing door open 90 degrees to load container.",
        ],
    },
    "sink": {
        "summary": "Single-lever mixer faucet controls volume via vertical lift and temperature via horizontal rotation.",
        "safety_guidelines": [
            "Direct nozzle spray downward into sink basin.",
            "Avoid overflowing counter edges during high-flow dispense.",
        ],
        "operating_steps": [
            "Lift faucet lever vertically to start water flow.",
            "Depress lever down to shut off flow completely.",
        ],
    },
}


class TavilyResearchAgent:
    """Autonomous research agent querying Tavily for physical appliance operating knowledge."""

    def __init__(self, log=print, cache_path: Path | str | None = None):
        self.log = log
        self.cache_path = Path(cache_path) if cache_path else DEFAULT_CACHE
        self._cache = self._load_cache()
        self.last_source: str = "uninitialized"

    def _load_cache(self) -> dict:
        if self.cache_path and self.cache_path.is_file():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception as e:
                self.log(f"[tavily] cache read error ({e}); using empty cache")
                return {}
        return {}

    def _save_cache(self) -> None:
        if not self.cache_path:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            self.log(f"[tavily] cache write warning: {e}")

    def search(self, query: str, search_depth: str = "basic") -> dict[str, Any]:
        """Search query with Tavily, checking cache first and falling back cleanly."""
        q_norm = query.strip().lower()
        if q_norm in self._cache:
            self.last_source = "cache"
            return dict(self._cache[q_norm])

        try:
            data = tavily_search(query, search_depth=search_depth, include_answer=True)
            res = {
                "source": "tavily_api",
                "answer": data.get("answer", ""),
                "results": data.get("results", []),
            }
            self.last_source = "tavily_api"
            self._cache[q_norm] = res
            self._save_cache()
            return res
        except TavilyNotConfigured as e:
            self.log(f"[tavily] API unconfigured ({e}); using domain fallback")
            self.last_source = "fallback"
            return {"source": "fallback", "answer": "", "results": []}
        except Exception as e:
            self.log(f"[tavily] search error ({e}); using domain fallback")
            self.last_source = "fallback"
            return {"source": "fallback", "answer": "", "results": []}

    def research_appliance(self, fixture_type: str) -> dict[str, Any]:
        """Synthesize operating knowledge and safety guidelines for an appliance."""
        key = fixture_type.lower()
        canonical = next((k for k in ("dishwasher", "stove", "fridge", "microwave", "sink") if k in key), "appliance")
        query = APPLIANCE_QUERIES.get(key, APPLIANCE_QUERIES.get(canonical, f"residential {key} appliance safe robot operation"))

        search_res = self.search(query)
        fallback = FALLBACK_KNOWLEDGE.get(canonical, FALLBACK_KNOWLEDGE.get(key, {}))

        summary = search_res.get("answer") or fallback.get("summary", f"Standard {fixture_type} fixture.")
        guidelines = list(fallback.get("safety_guidelines", [
            f"Maintain safe clearance from {fixture_type} surfaces.",
            f"Verify physical latches and joints before moving.",
        ]))
        operating_steps = list(fallback.get("operating_steps", [
            f"Approach {fixture_type} handle site.",
            f"Engage grip and execute trajectory along defined mechanical joint.",
        ]))
        sources = [r.get("url") for r in search_res.get("results", []) if r.get("url")]

        return {
            "fixture_type": fixture_type,
            "canonical_type": canonical,
            "query": query,
            "source": self.last_source,
            "summary": summary,
            "safety_guidelines": guidelines,
            "operating_steps": operating_steps,
            "sources": sources,
        }

    def enrich_twin(self, twin: dict) -> dict:
        """Scan digital twin fixtures and attach Tavily research for every appliance."""
        enriched = dict(twin)
        research: dict[str, dict] = {}

        for fx in twin.get("fixtures", []):
            ftype = fx.get("type", "")
            if ftype and ftype not in research:
                research[ftype] = self.research_appliance(ftype)

        enriched["tavily_research"] = research
        return enriched

    def get_prompt_context(self, fixture_type: str) -> str:
        """Returns a concise research summary suitable for injecting into LLM/VLM planning prompts."""
        info = self.research_appliance(fixture_type)
        lines = [
            f"Appliance Knowledge ({info['fixture_type']}): {info['summary']}",
            f"Safety Protocol: {'; '.join(info['safety_guidelines'])}",
        ]
        return "\n".join(lines)
