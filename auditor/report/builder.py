from __future__ import annotations
from pathlib import Path
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

def build_report(outdir: Path) -> None:
    flows = json.loads((outdir / "flows.json").read_text())
    
    # Copy mascot and logo images to report directory for consistent rendering
    import shutil
    mascot_src = Path("auditor/dashboard/static/uatu-mascot.png")
    if mascot_src.exists():
        shutil.copy2(mascot_src, outdir / "uatu-mascot.png")
    logo_src = Path("auditor/dashboard/static/uatu-logo.svg")
    if logo_src.exists():
        shutil.copy2(logo_src, outdir / "uatu-logo.svg")
    
    # Load test results if they exist
    test_runs = []
    test_dir = outdir / "runs" / "tests"
    if test_dir.exists():
        for f in test_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                # Ensure the test result has the expected structure
                if isinstance(data, dict):
                    # Add default values if missing
                    data.setdefault("passed", 0)
                    data.setdefault("failed", 0)
                    data.setdefault("tests", [])
                    data.setdefault("gas", {})
                    test_runs.append(data)
            except Exception as e:
                print(f"Warning: Failed to load test result {f}: {e}")
                pass
    
    env = Environment(
        loader=FileSystemLoader(str(Path("auditor/report/templates"))),
        autoescape=select_autoescape()
    )
    def load_json(path):
        try:
            return json.loads(Path(path).read_text())
        except Exception:
            return [] if path.endswith('.json') else {}
    
    # Compute gas top data
    gas_rows = []
    for r in test_runs:
        if isinstance(r, dict) and "gas" in r:
            for tname, g in (r.get("gas") or {}).items():
                try:
                    gas_rows.append({"journey": r.get("project", "unknown"), "test": tname, "gas": int(g)})
                except (ValueError, TypeError):
                    pass  # Skip invalid gas values
    gas_top = sorted(gas_rows, key=lambda x: x["gas"], reverse=True)[:10]

    # ----- LLM Assertions -----
    llm_meta = {"enabled": False, "provider":"none", "model":"", "reason":""}
    llm_dir = outdir / 'runs' / 'llm'
    if llm_dir.exists():
        m = llm_dir / 'meta.json'
        if m.exists():
            try: llm_meta = json.loads(m.read_text())
            except Exception: pass
    llm_rows = []
    llm_stats = {"added":0, "skipped":0, "error":0}
    if llm_dir.exists():
        for r in (llm_dir.glob('*.meta.json')):
            try:
                j = json.loads(r.read_text())
            except Exception:
                j = {}
            name = r.stem.replace('.meta','')
            llm_rows.append({"artifact": r.name, **j})
            rsn = (j.get('reason') or '').lower()
            if rsn in ('ok',): llm_stats['added'] += 1
            elif rsn in ('invalid_snippet','no_provider','disabled'): llm_stats['skipped'] += 1
            else:
                # treat compile_error and other unknowns as error
                llm_stats['error'] += 1

    # ----- Risk data loading -----
    risk = None
    rp = outdir / "runs" / "risk" / "risk.json"
    if rp.exists():
        try:
            risk = json.loads(rp.read_text())
        except Exception:
            pass

    risk_summary = (risk or {}).get("summary", {})
    risk_by_fn = (risk or {}).get("by_function", {})
    
    # ----- Risk trend data loading -----
    risk_trend = None
    trend_meta_path = outdir / "runs" / "risk" / "trend.meta.json"
    if trend_meta_path.exists():
        try:
            trend_meta = json.loads(trend_meta_path.read_text())
            history_path = outdir / "runs" / "risk" / "history.json"
            if history_path.exists():
                history = json.loads(history_path.read_text())
                risk_trend = {
                    "series": [(entry["ts"], entry["overall"]) for entry in history],
                    "meta": trend_meta,
                    "svg_data_uri": ""  # Will be populated if sparkline exists
                }
                
                # Try to load sparkline data URI
                sparkline_path = outdir / "sparkline-risk.svg"
                if sparkline_path.exists():
                    try:
                        svg_content = sparkline_path.read_text()
                        import base64
                        svg_bytes = svg_content.encode('utf-8')
                        data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('utf-8')}"
                        risk_trend["svg_data_uri"] = data_uri
                    except Exception:
                        pass
        except Exception:
            pass
    
    # build heatmap rows: list of dicts {contract, function, score, grade, delta, cats}
    heatmap = []
    stride_badges = {}
    if risk_by_fn:
        for k, v in risk_by_fn.items():
            heatmap.append({
                "contract": v["contract"], "function": v["function"],
                "score": v["score"], "grade": v["grade"],
                "delta": v.get("delta", 0.0),
                "cats": v["evidence"].get("stride_categories") or []
            })
        # sort desc
        heatmap.sort(key=lambda x: x["score"], reverse=True)

        # STRIDE badge colors
        stride_badges = {
            "elevation_of_privilege": "#f8d7da",
            "tampering": "#fde2cf",
            "information_disclosure": "#e2f0ff",
            "spoofing": "#e8e8ff",
            "denial_of_service": "#fff4cc",
            "repudiation": "#f0f0f0",
        }

    # ----- EoP Coverage computation -----
    # load modes/meta
    eop_mode = 'auto'
    tests_meta = outdir / 'runs' / 'tests' / 'meta.json'
    if tests_meta.exists():
        try:
            eop_mode = (json.loads(tests_meta.read_text()) or {}).get('eop_mode','auto')
        except Exception:
            pass

    # load threats for stride
    threats = {}
    tfile = outdir / 'threats.json'
    if tfile.exists():
        try:
            threats = json.loads(tfile.read_text())
        except Exception:
            threats = {}

    # heuristic prefixes (mirror of generator)
    SENSITIVE_PREFIXES = [
        'withdraw','sweep','rescue','mint','burn','pause','unpause',
        'upgrade','authorize','deauthorize','grantrole','revokerole',
        'setowner','transferownership','setadmin','setguardian','emergency',
        'setfee','settreasury','setwhitelist','addwhitelist','removewhitelist'
    ]
    def _is_sensitive_fn(fn: str) -> bool:
        fl = (fn or '').lower()
        return any(fl == p or fl.startswith(p) for p in SENSITIVE_PREFIXES)

    # build candidate set (depends on eop_mode)
    candidates = []  # rows: {contract,function,gating}
    for c in (flows.get('contracts') or []):
        cname = c.get('name')
        for f in (c.get('functions') or []):
            fname = f.get('name')
            key = f"{cname}.{fname}"
            has_stride = False
            if isinstance(threats, dict):
                b = (threats.get('by_function') or {}).get(key, {})
                has_stride = len((b or {}).get('elevation_of_privilege') or []) > 0
            has_heur = _is_sensitive_fn(fname)
            m = (eop_mode or 'auto').lower()
            gated = False
            src = 'none'
            if m == 'off':
                gated = False
            elif m == 'stride':
                gated = has_stride; src = 'stride'
            elif m == 'heuristic':
                gated = has_heur; src = 'heuristic'
            elif m == 'both':
                gated = has_stride or has_heur; src = 'stride+heuristic' if (has_stride and has_heur) else ('stride' if has_stride else ('heuristic' if has_heur else 'none'))
            else:  # auto
                if has_stride: gated = True; src = 'stride'
                elif has_heur: gated = True; src = 'heuristic'
            if gated:
                candidates.append({'contract': cname, 'function': fname, 'gating': src})

    # map test runs -> presence/status of eop tests
    # project name convention from generator: e.g., happy_Contract_function
    eop_rows = []
    for row in candidates:
        proj = f"happy_{row['contract']}_{row['function']}"
        tr = next((r for r in test_runs if isinstance(r, dict) and r.get('project') == proj), None)
        tested = False; status = None
        if tr and isinstance(tr, dict):
            names = [t.get('name','') for t in (tr.get('tests') or []) if isinstance(t, dict)]
            # exact eop test name pattern:
            target = f"test_eop_block_{row['function']}"
            matched = [n for n in names if n == target]
            if matched:
                tested = True
                stat = next((t for t in tr.get('tests') or [] if isinstance(t, dict) and t.get('name')==target), {})
                status = stat.get('status') if isinstance(stat, dict) else None
        eop_rows.append({**row, 'project': proj, 'tested': tested, 'status': status})

    # Load static analysis metadata
    static_meta = {}
    sm = outdir / 'runs' / 'static' / 'metadata.json'
    if sm.exists():
        try: 
            static_meta = json.loads(sm.read_text())
        except Exception: 
            static_meta = {}
    
    # Load findings from Slither
    findings = []
    slither_norm = outdir / 'runs' / 'static' / 'slither.normalized.json'
    if slither_norm.exists():
        try:
            findings = json.loads(slither_norm.read_text())
            if not isinstance(findings, list):
                findings = []
        except Exception:
            findings = []

    md = env.get_template("report.md.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta, eop_rows=eop_rows, eop_mode=eop_mode, llm_meta=llm_meta, llm_rows=llm_rows, llm_stats=llm_stats, risk=risk, risk_summary=risk_summary, risk_heatmap=heatmap, stride_badges=stride_badges, risk_trend=risk_trend)
    html = env.get_template("report.html.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta, eop_rows=eop_rows, eop_mode=eop_mode, llm_meta=llm_meta, llm_rows=llm_rows, llm_stats=llm_stats, risk=risk, risk_summary=risk_summary, risk_heatmap=heatmap, stride_badges=stride_badges, risk_trend=risk_trend)
    (outdir / "report.md").write_text(md)
    (outdir / "report.html").write_text(html)
    
    # Generate PDF with compact data
    pdf_env = Environment(
        loader=FileSystemLoader(str(Path("auditor/templates/pdf"))),
        autoescape=select_autoescape()
    )
    
    # Prepare PDF data
    pdf_data = {
        "title": "Uatu Audit Report",
        "report_kind": "Smart Contract Security Analysis",
        "contract_id": flows.get("contracts", [{}])[0].get("name", "Unknown") if flows.get("contracts") else "Unknown",
        "commit": "N/A",  # Could be extracted from git if available
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": risk_summary or {},
        "risk_top": heatmap[:10] if heatmap else [],
        "risk_heatmap": heatmap if heatmap else [],
        "tests": {
            "passed": sum(r.get("passed", 0) for r in test_runs if isinstance(r, dict)),
            "total": sum(r.get("passed", 0) + r.get("failed", 0) for r in test_runs if isinstance(r, dict)),
            "journeys": len(test_runs)
        },
        "eop": {
            "total": len(eop_rows),
            "covered": len([r for r in eop_rows if r.get("tested")])
        },
        "llm": {
            "status": "enabled" if llm_meta.get("enabled") else "disabled"
        },
        "static": {
            "status": "ok" if static_meta.get("ok", True) else "failed",
            "findings": len(findings)
        },
        "gas": {
            "top_fn": gas_top[0].get("test", "-") if gas_top else "-",
            "top_val": gas_top[0].get("gas", "-") if gas_top else "-"
        },
        "findings": findings[:20] if findings else [],  # Limit for PDF
        "sparkline_data_uri": risk_trend.get("svg_data_uri", "") if risk_trend else "",
        "versions": {"tool": "UatuAudit v2.0"},
        "modes": static_meta.get("mode", "Standard"),
        "year": __import__("datetime").datetime.now().year
    }
    
    pdf_html = pdf_env.get_template("report.html.j2").render(**pdf_data, asset_base=str(outdir))
    (outdir / "report_pdf.html").write_text(pdf_html)
    
    # also write report.json placeholder
    (outdir / "report.json").write_text(json.dumps({"summary":"Task 6 with real Slither integration"}, indent=2))
