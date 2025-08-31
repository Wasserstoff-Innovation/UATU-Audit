from __future__ import annotations
from pathlib import Path
import json, math
from typing import Dict, Any, Tuple, List

DEFAULT_WEIGHTS = {
  "static": {"critical":10, "high":7, "medium":4, "low":1, "info":0.5},
  "stride": {
    "elevation_of_privilege":7, "tampering":6, "information_disclosure":6,
    "spoofing":6, "denial_of_service":3, "repudiation":2
  },
  "tests": {"eop_failed":8, "neg_failed":5, "stress_failed":3},
  "gas": {"heavy_threshold": 200000, "penalty": 1},  # minimal nudge
  "scaling": {"function_cap": 100, "journey_cap": 100}
}

SEV_MAP_IN = {  # normalize various inputs to static severities
  "critical":"critical","severe":"critical","high":"high","med":"medium",
  "medium":"medium","low":"low","info":"info","informational":"info"
}

def _grade(score: float) -> str:
    if score >= 90: return "Critical"
    if score >= 75: return "High"
    if score >= 50: return "Medium"
    if score >= 25: return "Low"
    return "Info"

def export_heatmap_csv(outdir: Path, by_function: dict):
    """Export risk heatmap to CSV format."""
    rows = []
    for k, v in by_function.items():
        rows.append([
            v["contract"], v["function"],
            v["score"], v["grade"], v.get("delta", 0.0),
            ",".join(v["evidence"].get("stride_categories") or [])
        ])
    csvp = outdir / "runs" / "risk" / "heatmap.csv"
    csvp.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["contract","function","score","grade","delta","stride_cats"])
        w.writerows(rows)

def _load_json(p: Path) -> Any:
    return json.loads(p.read_text()) if p.exists() else None

def _collect_static(findings_norm: dict | None) -> Dict[str, List[Dict]]:
    """Return mapping funcKey -> [finding,...]. Fallback to contract-level if function not resolvable."""
    out: Dict[str, List[Dict]] = {}
    if not findings_norm: return out
    for f in findings_norm.get("findings", []):
        sev = SEV_MAP_IN.get(str(f.get("severity","")).lower(), "info")
        where = f.get("function") or ""  # if your normalization includes function; else keep empty
        contract = f.get("contract") or ""
        key = where or (contract + ".*" if contract else "*")
        out.setdefault(key, []).append({"severity": sev, "rule": f.get("check") or f.get("id") or ""})
    return out

def _static_points(items: List[Dict], w) -> float:
    pts = 0.0
    for it in items:
        pts += w["static"].get(it["severity"], 0)
    return pts

def _stride_points(threats_for_fn: Dict[str, List[str]] | None, w) -> float:
    if not threats_for_fn: return 0.0
    pts = 0.0
    for cat, lst in threats_for_fn.items():
        pts += w["stride"].get(cat, 0) * (1 if lst else 0)  # presence-based
    return pts

def _tests_points(test_metrics: Dict[str,int], w) -> float:
    pts = 0.0
    pts += test_metrics.get("eop_failed", 0) * w["tests"]["eop_failed"]
    pts += test_metrics.get("neg_failed", 0) * w["tests"]["neg_failed"]
    pts += test_metrics.get("stress_failed", 0) * w["tests"]["stress_failed"]
    return pts

def _gas_points(gas_map: Dict[str,int], w) -> float:
    # very soft: each test > threshold adds 1
    thr = w["gas"]["heavy_threshold"]; pen = w["gas"]["penalty"]
    return sum(1 for v in gas_map.values() if isinstance(v, int) and v > thr) * pen

def _function_key(contract: str, fn: str) -> str:
    return f"{contract}.{fn}"

def score(
    outdir: Path,
    flows: dict, threats: dict | None,
    slither_norm: dict | None,
    test_runs: dict | None,
    risk_config_path: Path | None = None,
    baseline: dict | None = None,
    export_csv: bool = False
) -> dict:
    # weights
    weights = DEFAULT_WEIGHTS.copy()
    if risk_config_path and risk_config_path.exists():
        user = json.loads(risk_config_path.read_text())
        # shallow merge is fine
        for k,v in (user or {}).items():
            if isinstance(v, dict) and k in weights:
                weights[k].update(v)
            else:
                weights[k] = v

    # prep maps
    static_map = _collect_static(slither_norm)
    threats_by_fn = (threats or {}).get("by_function") or {}
    tests_dir = outdir / "runs" / "tests"
    tests_index = {}   # fnKey -> metrics + gas
    if tests_dir.exists():
        for jf in tests_dir.glob("*.json"):
            j = _load_json(jf) or {}
            # journey scope — derive per-function failures best-effort
            journey_id = j.get("journey") or jf.stem
            passed = j.get("passed", 0); failed = j.get("failed", 0)
            gas = j.get("gas", {})
            # derive which function this journey belongs to (heuristic: after first '_', last segment)
            # Better: parse flows/journeys, but minimal viable:
            for c in flows.get("contracts", []):
                cname = c.get("name")
                for fn in (c.get("functions") or []):
                    fname = fn.get("name")
                    if fname and fname in journey_id:
                        key = _function_key(cname, fname)
                        m = tests_index.setdefault(key, {"eop_failed":0,"neg_failed":0,"stress_failed":0,"gas":{}})
                        # map by test names if present
                        failures = j.get("tests", [])
                        for t_res in failures:
                            t_name = t_res.get("name", "")
                            if t_name.startswith("test_eop_") and t_res.get("status") == "failed":
                                m["eop_failed"] += 1
                            elif t_name.startswith("test_negative_") and t_res.get("status") == "failed":
                                m["neg_failed"] += 1
                            elif t_name.startswith("test_stress_") and t_res.get("status") == "failed":
                                m["stress_failed"] += 1
                        # merge gas
                        if isinstance(gas, dict):
                            m["gas"].update(gas)

    # per-function scoring
    by_function = {}
    for c in flows.get("contracts", []):
        cname = c.get("name")
        for f in (c.get("functions") or []):
            fname = f.get("name")
            key = _function_key(cname, fname)
            # static
            stat_items = static_map.get(key, []) + static_map.get(cname+".*", []) + static_map.get("*", [])
            stat_pts = _static_points(stat_items, weights)
            # stride
            th_bucket = threats_by_fn.get(key, {})
            stride_pts = _stride_points(th_bucket, weights)
            # tests
            tmet = tests_index.get(key, {"eop_failed":0,"neg_failed":0,"stress_failed":0,"gas":{}})
            test_pts = _tests_points(tmet, weights)
            # gas
            gas_pts = _gas_points(tmet.get("gas", {}), weights)
            raw = stat_pts + stride_pts + test_pts + gas_pts
            score_val = min(weights["scaling"]["function_cap"], raw)
            by_function[key] = {
                "contract": cname, "function": fname,
                "score": round(score_val, 1),
                "grade": _grade(score_val),
                "evidence": {
                    "static_findings": stat_items,
                    "stride_categories": [k for k,v in (th_bucket or {}).items() if v],
                    "test_metrics": {k:v for k,v in tmet.items() if k!="gas"},
                    "gas": tmet.get("gas", {})
                }
            }

    # per-journey scoring (sum constituent function scores; light path factor)
    journeys = ( _load_json(outdir / "journeys.json") or {}).get("journeys", [])
    by_journey = {}
    for j in journeys:
        jid = j.get("id") or "_".join([j["steps"][0]["call"]["contract"], j["steps"][0]["call"]["function"]]) if j.get("steps") else "journey"
        fns = []
        for st in (j.get("steps") or []):
            call = st.get("call") or {}
            k = _function_key(call.get("contract",""), call.get("function",""))
            if k in by_function:
                fns.append(k)
        raw = sum(by_function[k]["score"] for k in fns)
        # soft path factor: +1 per additional hop beyond first, capped
        raw += max(0, len(fns)-1) * 2
        score_val = min(weights["scaling"]["journey_cap"], raw)
        by_journey[jid] = {
            "score": round(score_val, 1),
            "grade": _grade(score_val),
            "functions": fns
        }

    # summary
    fn_scores = [v["score"] for v in by_function.values()]
    overall = round(sum(fn_scores)/len(fn_scores), 1) if fn_scores else 0.0
    
    # grade bucket counts
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    for v in by_function.values():
        grade = v["grade"]
        if grade in buckets:
            buckets[grade] += 1
    
    summary = {
        "overall": overall,
        "grade": _grade(overall),
        "buckets": buckets,
        "top_functions": sorted(
            [{"key":k, "score":v["score"], "grade":v["grade"]} for k,v in by_function.items()],
            key=lambda x: x["score"], reverse=True
        )[:10]
    }

    # apply baseline deltas (if provided)
    base_by_fn = (baseline or {}).get("by_function", {})
    for k, v in by_function.items():
        prev = (base_by_fn.get(k) or {}).get("score", 0.0)
        v["delta"] = round(v["score"] - float(prev), 1)
    
    # per-journey deltas
    base_by_journey = (baseline or {}).get("by_journey", {})
    for k, v in by_journey.items():
        prev = (base_by_journey.get(k) or {}).get("score", 0.0)
        v["delta"] = round(v["score"] - float(prev), 1)
    
    # overall delta
    base_overall = (baseline or {}).get("summary", {}).get("overall", 0.0)
    summary["delta_overall"] = round(summary["overall"] - float(base_overall), 1)

    # CSV export if requested
    if export_csv:
        export_heatmap_csv(outdir, by_function)

    return {
        "version":"1",
        "weights": weights,
        "by_function": by_function,
        "by_journey": by_journey,
        "summary": summary
    }
