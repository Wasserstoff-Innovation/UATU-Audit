from __future__ import annotations
from pathlib import Path
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

def build_report(outdir: Path) -> None:
    flows = json.loads((outdir / "flows.json").read_text())
    
    # Load test results if they exist
    test_runs = []
    test_dir = outdir / "runs" / "tests"
    if test_dir.exists():
        for f in test_dir.glob("*.json"):
            try:
                test_runs.append(json.loads(f.read_text()))
            except Exception:
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
        for tname, g in (r.get("gas") or {}).items():
            gas_rows.append({"journey": r.get("project"), "test": tname, "gas": int(g)})
    gas_top = sorted(gas_rows, key=lambda x: x["gas"], reverse=True)[:10]

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
        tr = next((r for r in test_runs if r.get('project') == proj), None)
        tested = False; status = None
        if tr:
            names = [t.get('name','') for t in (tr.get('tests') or [])]
            # exact eop test name pattern:
            target = f"test_eop_block_{row['function']}"
            matched = [n for n in names if n == target]
            if matched:
                tested = True
                stat = next((t for t in tr.get('tests') or [] if t.get('name')==target), {})
                status = stat.get('status')
        eop_rows.append({**row, 'project': proj, 'tested': tested, 'status': status})

    # Load static analysis metadata
    static_meta = {}
    sm = outdir / 'runs' / 'static' / 'metadata.json'
    if sm.exists():
        try: 
            static_meta = json.loads(sm.read_text())
        except Exception: 
            static_meta = {}

    md = env.get_template("report.md.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta, eop_rows=eop_rows, eop_mode=eop_mode)
    html = env.get_template("report.html.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta, eop_rows=eop_rows, eop_mode=eop_mode)
    (outdir / "report.md").write_text(md)
    (outdir / "report.html").write_text(html)
    # also write report.json placeholder
    (outdir / "report.json").write_text(json.dumps({"summary":"Task 6 with real Slither integration"}, indent=2))
