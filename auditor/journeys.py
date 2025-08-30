from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
from .stride import expand_journeys

def base_happy_journeys(flows: Dict[str, Any]) -> Dict[str, Any]:
    journeys = {"journeys": []}
    for c in flows.get("contracts", []):
        cname = c["name"]
        for fn in c.get("functions", []):
            vis = (fn.get("visibility") or "").lower()
            if vis in ("public","external"):
                journeys["journeys"].append({
                    "id": f"happy_{cname}_{fn['name']}",
                    "tags": ["happy"],
                    "chain": "evm",
                    "steps": [{"contract": cname, "function": fn["name"], "actor": "User"}]
                })
    return journeys

def make_journeys(flows: Dict[str, Any]) -> Dict[str, Any]:
    base = base_happy_journeys(flows)
    return expand_journeys(flows, base)
