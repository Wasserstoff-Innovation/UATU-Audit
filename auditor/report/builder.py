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

    # Load static analysis metadata
    static_meta = {}
    sm = outdir / 'runs' / 'static' / 'metadata.json'
    if sm.exists():
        try: 
            static_meta = json.loads(sm.read_text())
        except Exception: 
            static_meta = {}

    md = env.get_template("report.md.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta)
    html = env.get_template("report.html.j2").render(flows=flows, outdir=str(outdir), load_json=load_json, test_runs=test_runs, gas_top=gas_top, static_meta=static_meta)
    (outdir / "report.md").write_text(md)
    (outdir / "report.html").write_text(html)
    # also write report.json placeholder
    (outdir / "report.json").write_text(json.dumps({"summary":"Task 6 with real Slither integration"}, indent=2))
