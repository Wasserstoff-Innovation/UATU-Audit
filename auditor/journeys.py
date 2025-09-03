from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
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

def make_journeys(flows: Dict[str, Any], clusters=None) -> Dict[str, Any]:
    # Deterministic baseline: happy + auth-negative for privileged modifiers + simple stress
    base = base_happy_journeys(flows)
    journeys: List[Dict[str, Any]] = list(base.get("journeys", []))
    
    # Use clustering information if available to enhance journey planning
    if clusters and hasattr(clusters, 'features'):
        for feature in clusters.features:
            # Create feature-based journeys using preconditions and fixtures
            if len(feature.fns) > 1:
                # Multi-function feature journey
                steps = []
                for fn in feature.fns:
                    # Find the contract for this function
                    contract_name = None
                    for c in flows.get("contracts", []):
                        for contract_fn in c.get("functions", []):
                            if contract_fn.get("name") == fn:
                                contract_name = c.get("name")
                                break
                        if contract_name:
                            break
                    
                    if contract_name:
                        steps.append({
                            "contract": contract_name,
                            "function": fn,
                            "actor": "User"
                        })
                
                if steps:
                    journeys.append({
                        "id": f"feature_{feature.name.lower().replace(' ', '_')}",
                        "tags": ["feature", "clustered"],
                        "chain": "evm",
                        "steps": steps,
                        "preconditions": feature.preconds,
                        "fixture": feature.fixture
                    })
    # auth-negative
    for c in flows.get("contracts", []):
        cname = c.get("name","")
        for fn in c.get("functions", []):
            mods = [m.lower() for m in (fn.get("modifiers") or [])]
            privileged = any(k in mods for k in ["onlyowner","onlyrole","admin"])
            if privileged:
                journeys.append({
                    "id": f"authneg_{cname}_{fn['name']}",
                    "tags": ["negative","auth"],
                    "chain": "evm",
                    "steps": [
                        {"contract": cname, "function": fn["name"], "actor": "Attacker", "expectRevert": True}
                    ]
                })
    # stress (simple): if a mapping/array hint is present, add loop call seeds
    for c in flows.get("contracts", []):
        cname = c.get("name","")
        for fn in c.get("functions", []):
            if "count" in (fn.get("name","")).lower() or "batch" in (fn.get("name","")).lower():
                journeys.append({
                    "id": f"stress_{cname}_{fn['name']}",
                    "tags": ["stress"],
                    "chain": "evm",
                    "steps": [
                        {"contract": cname, "function": fn["name"], "actor": "User", "repeat": 50}
                    ]
                })
    capped = {"journeys": journeys[:40]}
    return expand_journeys(flows, capped)
