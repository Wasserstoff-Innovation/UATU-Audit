from __future__ import annotations
import json, re
from pathlib import Path
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict

# --- Normalize Slither JSON to a uniform list of findings ---
def normalize_slither(slither_json_path: Path) -> List[Dict[str, Any]]:
    try:
        raw = json.loads(slither_json_path.read_text())
    except Exception:
        return []
    detectors = raw.get("results", {}).get("detectors") or raw.get("detectors") or []
    findings = []
    for d in detectors:
        check = (d.get("check") or d.get("check_id") or "").lower()
        impact = (d.get("impact") or d.get("severity") or "Info").capitalize()
        desc = d.get("description") or d.get("impact") or check
        elements = d.get("elements") or []
        # Try to get function/contract/file info
        fn = None
        contract = None
        file = None
        line = None
        for e in elements:
            e_name = (e.get("name") or "").strip()
            e_type = (e.get("type") or "").lower()
            sm = e.get("source_mapping") or {}
            file = file or sm.get("filename_relative") or sm.get("filename_absolute")
            line = line or (sm.get("lines") or [None])[0]
            if e_type == "function":
                fn = e_name or fn
            if e_type == "contract":
                contract = e_name or contract
        findings.append({
            "tool": "slither",
            "check": check,
            "severity": impact,
            "title": desc.split("\n")[0][:200],
            "contract": contract,
            "function": fn,
            "location": f"{file}:{line}" if file else None,
        })
    return findings

# --- Map normalized findings to STRIDE categories ---
# (very lightweight keyword mapping by check name)
MAP = [
    ("reentrancy", "tampering"),
    ("unchecked", "tampering"),
    ("arbitrary-send", "tampering"),
    ("delegatecall", "elevation_of_privilege"),
    ("tx.origin", "spoofing"),
    ("auth", "spoofing"),
    ("access control", "elevation_of_privilege"),
    ("selfdestruct", "tampering"),
    ("denial", "denial_of_service"),
    ("dos", "denial_of_service"),
    ("unbounded", "denial_of_service"),
    ("timestamp", "tampering"),
    ("block.number", "tampering"),
    ("event missing", "repudiation"),
    ("missing event", "repudiation"),
    ("information", "information_disclosure"),
    ("leak", "information_disclosure"),
]

def map_findings_to_stride(findings: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    # returns: { "Contract.func": { category: [messages] } }
    out: Dict[str, Dict[str, List[str]]] = {}
    def ensure(k):
        if k not in out:
            out[k] = { "spoofing":[], "tampering":[], "repudiation":[], "information_disclosure":[], "denial_of_service":[], "elevation_of_privilege":[] }
    for f in findings:
        key = None
        if f.get("contract") and f.get("function"):
            key = f"{f['contract']}.{f['function']}"
        elif f.get("contract"):
            key = f"{f['contract']}."
        else:
            key = "global"
        ensure(key)
        check = f.get("check","")
        cat = None
        lc = check.lower()
        for kw, catname in MAP:
            if kw in lc:
                cat = catname
                break
        # default bucket if unknown: tampering for unsafe patterns, otherwise info_disclosure
        cat = cat or ("tampering" if "unsafe" in lc or "unchecked" in lc else "information_disclosure")
        msg = f"{f['severity']}: {f['title']}"
        out[key][cat].append(msg)
    return out

# --- Expand journeys deterministically ---
ADMINY = re.compile(r"^(set|grant|revoke|pause|unpause|mint|burn|upgrade|owner|admin)", re.I)
HEAVY_NAMES = re.compile(r"(transfer|mint|burn|loop|bulk|batch|distribute)", re.I)

def expand_journeys(flows: Dict[str, Any], base: Dict[str, Any]) -> Dict[str, Any]:
    journeys = list(base.get("journeys", []))
    # Negative: unauth for admin-y names
    for c in flows.get("contracts", []):
        cname = c["name"]
        for fn in c.get("functions", []):
            vis = (fn.get("visibility") or "").lower()
            if vis in ("public","external"):
                if ADMINY.search(fn["name"]):
                    journeys.append({
                        "id": f"negative_unauth_{cname}_{fn['name']}",
                        "tags": ["negative","auth"],
                        "chain": "evm",
                        "steps": [{"contract": cname, "function": fn["name"], "actor": "Attacker"}]
                    })
                # Stress: heavy call patterns or amount-like args
                if HEAVY_NAMES.search(fn["name"]) or any("uint" in (arg.get("type","")) and arg.get("name","").lower() in ("amount","value","qty","quantity") for arg in fn.get("inputs",[])):
                    journeys.append({
                        "id": f"stress_{cname}_{fn['name']}",
                        "tags": ["stress","dos"],
                        "chain": "evm",
                        "steps": [{"contract": cname, "function": fn["name"], "actor": "User"}]
                    })
    return {"journeys": dedupe_by_id(journeys)}

def dedupe_by_id(items: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    seen, out = set(), []
    for j in items:
        if j["id"] in seen: 
            continue
        seen.add(j["id"]); out.append(j)
    return out

# --- Merge STRIDE by_function with empty categories for all functions (nice, safe output) ---
def stitch_threats(flows: Dict[str,Any], mapped: Dict[str,Dict[str,List[str]]]) -> Dict[str,Any]:
    by_fn: Dict[str, Dict[str, List[str]]] = {}
    def empty_buckets():
        return {"spoofing":[], "tampering":[], "repudiation":[], "information_disclosure":[], "denial_of_service":[], "elevation_of_privilege":[]}
    # Ensure every function key is present with empty arrays if nothing found
    for c in flows.get("contracts", []):
        cname = c["name"]
        for fn in c.get("functions", []):
            key = f"{cname}.{fn['name']}"
            by_fn[key] = empty_buckets()
    # Overlay mapped
    for k, cats in mapped.items():
        if k not in by_fn:
            by_fn[k] = empty_buckets()
        for cat, msgs in cats.items():
            by_fn[k][cat].extend(msgs)
    return {"by_function": by_fn, "by_journey": {}}
