from __future__ import annotations
from pathlib import Path
from datetime import datetime
import os

from .utils import (
    is_eth_address, copy_source_to_work, etherscan_fetch_sources,
    json_dump_atomic, validate_json
)
from .flows import extract_flows_from_dir
from .runners.slither_runner import run_slither
from .stride import normalize_slither, map_findings_to_stride, stitch_threats
from .journeys import make_journeys
from .testgen.foundry import generate_foundry_tests
from .runners.forge_runner import run_forge_tests
from .testgen.soroban import generate_soroban_tests
from .runners.cargo_runner import run_cargo_tests
from .llm.engine import detect_provider, LLMMeta
from .risk.scoring import score as risk_score

class Orchestrator:
    def __init__(self, input_path_or_address: str, kind: str = "evm", out_root: Path = Path("out"), llm: bool = False, static_mode: str = "auto", eop_mode: str = "auto", llm_provider: str = "auto", llm_model: str = "", risk: bool = True, risk_config_path: str | None = None, risk_baseline: str | None = None, risk_export: str = "csv", badge: bool = True, trend: bool = True, trend_n: int = 10, pdf: bool = True):
        self.input = input_path_or_address
        self.kind = kind
        self.out_root = out_root
        self.llm = llm
        self.static_mode = static_mode
        self.eop_mode = eop_mode
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.risk = risk
        self.risk_config_path = risk_config_path
        self.risk_baseline = risk_baseline
        self.risk_export = risk_export
        self.badge = badge
        self.trend = trend
        self.trend_n = trend_n
        self.pdf = pdf

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.outdir = out_root / ts
        self.workdir = self.outdir / "work"
        self.srcdir = self.workdir / "src"
        (self.outdir / "runs").mkdir(parents=True, exist_ok=True)

    def _build_abi_map(self, flows: dict) -> dict:
        abi = {"functions": {}, "events": {}, "errors": {}}
        for c in (flows.get("contracts") or []):
            cname = c.get("name")
            for f in (c.get("functions") or []):
                key = f"{cname}.{f.get('name')}"
                abi["functions"][key] = [{"name": i.get("name",""), "type": i.get("type","")} for i in (f.get("inputs") or [])]
            for e in (c.get("events") or []):
                en = e.get("name")
                # Parse event params from string format like "address indexed caller"
                event_params = []
                for param_str in (e.get("params") or []):
                    parts = param_str.split()
                    if len(parts) >= 2:
                        param_type = parts[0]
                        param_name = parts[-1]
                        indexed = "indexed" in parts
                        event_params.append({"name": param_name, "type": param_type, "indexed": indexed})
                abi["events"].setdefault(cname, {})[en] = event_params
        # (Optional) custom errors: if your flows capture them, fill here; keep empty otherwise
        return abi

    def _save_abi_map(self, abi: dict):
        d = self.outdir / "runs" / "llm"
        d.mkdir(parents=True, exist_ok=True)
        (d/"abi.json").write_text(__import__("json").dumps(abi, indent=2))

    def _prepare(self) -> None:
        if self.kind not in ["evm", "stellar"]:
            raise NotImplementedError("Task 7 supports EVM and stellar (Rust) only for now.")
        if Path(self.input).exists():
            copy_source_to_work(self.input, self.srcdir)
        else:
            # assume eth address (only for EVM)
            if self.kind == "evm":
                if not is_eth_address(self.input):
                    raise ValueError("Input is neither a file/folder nor a valid Ethereum address.")
                api_key = os.environ.get("ETHERSCAN_API_KEY")
                etherscan_fetch_sources(self.input, api_key, self.workdir)
                # put files under srcdir consistently
                # if fetch placed under work/sources, mirror them into src/
                src_root = self.workdir / "sources"
                if src_root.exists():
                    copy_source_to_work(str(src_root), self.srcdir)
            else:
                raise ValueError("stellar kind requires a file path, not an address.")

    def _explore(self) -> dict:
        flows = extract_flows_from_dir(self.srcdir, kind=self.kind)
        # validate and write
        validate_json(flows, Path("auditor/schemas/flows.schema.json"))
        json_dump_atomic(self.outdir / "flows.json", flows)
        return flows

    def _journeys(self, flows: dict) -> dict:
        journeys = make_journeys(flows)
        validate_json(journeys, Path("auditor/schemas/journeys.schema.json"))
        json_dump_atomic(self.outdir / "journeys.json", journeys)
        return journeys

    def _threats(self, flows: dict, journeys: dict) -> dict:
        # Run Slither (Docker). Always write something even on failure.
        static_dir = self.outdir / "runs" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        res = run_slither(self.srcdir, static_dir, mode=self.static_mode)
        findings = []
        if res.get("ok"):
            norm = normalize_slither(Path(res["path"]))
            (static_dir / "slither.normalized.json").write_text(__import__("json").dumps(norm, indent=2))
            findings = norm
        # Map to STRIDE and stitch with empty buckets for all functions
        mapped = map_findings_to_stride(findings)
        threats = stitch_threats(flows, mapped)
        validate_json(threats, Path("auditor/schemas/threats.schema.json"))
        json_dump_atomic(self.outdir / "threats.json", threats)
        return threats

    def _generate_tests(self, flows: dict, journeys: dict, threats: dict) -> dict:
        provider_meta = detect_provider(self.llm_provider if self.llm else "off")
        # allow override model
        if self.llm and self.llm_model:
            provider_meta.model = self.llm_model
        # persist llm meta
        meta_dir = self.outdir / "runs" / "llm"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta.json").write_text(__import__("json").dumps({
            "enabled": provider_meta.enabled,
            "provider": provider_meta.provider,
            "model": provider_meta.model,
            "reason": provider_meta.reason
        }, indent=2))
        
        # build and save ABI map for EVM contracts
        abi_map = self._build_abi_map(flows) if self.kind == "evm" else {}
        if abi_map:
            self._save_abi_map(abi_map)
        
        tests = {"tests": []}
        if self.kind == "evm":
            tests = generate_foundry_tests(flows, journeys, self.srcdir, self.outdir,
                                         threats=threats, eop_mode=self.eop_mode,
                                         llm_meta=provider_meta, abi_map=abi_map)
        elif self.kind == "stellar":
            tests = generate_soroban_tests(flows, journeys, self.srcdir, self.outdir)
        # persist test meta (e.g., eop_mode)
        meta_dir = self.outdir / "runs" / "tests"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta.json").write_text(__import__("json").dumps({"eop_mode": self.eop_mode}, indent=2))
        return tests

    def _run_tests(self) -> dict:
        results = {"runs": []}
        test_root = self.outdir / "tests" / ("evm" if self.kind=="evm" else "soroban")
        runs_dir = self.outdir / "runs" / "tests"
        if test_root.exists():
            for proj in sorted(test_root.iterdir()):
                if not proj.is_dir(): continue
                out_file = runs_dir / f"{proj.name}.json"
                if self.kind == "evm":
                    res = run_forge_tests(proj, out_file)
                else:
                    res = run_cargo_tests(proj, out_file)
                results["runs"].append(res)
        return results

    def _compute_and_save_risk(self, flows, threats):
        runs_dir = self.outdir / "runs"
        risk_dir = runs_dir / "risk"
        risk_dir.mkdir(parents=True, exist_ok=True)

        slither_norm = (runs_dir / "static" / "slither.normalized.json")
        slither_norm_j = __import__("json").loads(slither_norm.read_text()) if slither_norm.exists() else None

        # Load baseline if provided
        base = None
        if self.risk_baseline:
            bp = Path(self.risk_baseline)
            if bp.exists():
                base = __import__("json").loads(bp.read_text())

        # Aggregate tests (you already write one file per journey)
        # Optionally pass None; scorer will read runs/tests/*.json by itself using outdir.
        res = risk_score(
            outdir=self.outdir,
            flows=flows,
            threats=threats,
            slither_norm=slither_norm_j,
            test_runs=None,
            risk_config_path=Path(self.risk_config_path) if self.risk_config_path else None,
            baseline=base,
            export_csv=(self.risk_export == "csv"),
        )

        (risk_dir / "risk.json").write_text(__import__("json").dumps(res, indent=2))
        # optional schema validation
        schema_path = Path("auditor/schemas/risk.schema.json")
        if schema_path.exists():
            validate_json(res, schema_path)

    def _load_history(self) -> list:
        """Load best available history: baseline first, then local fallback."""
        history = []
        
        # Try baseline history first
        if self.risk_baseline:
            baseline_dir = Path(self.risk_baseline).parent
            baseline_id = baseline_dir.name.replace(".risk.json", "")
            baseline_history_path = baseline_dir / f"{baseline_id}.history.json"
            if baseline_history_path.exists():
                try:
                    history = __import__("json").loads(baseline_history_path.read_text())
                    return history
                except Exception:
                    pass
        
        # Fallback to local history if available
        local_history_path = self.outdir / "runs" / "risk" / "history.json"
        if local_history_path.exists():
            try:
                history = __import__("json").loads(local_history_path.read_text())
            except Exception:
                pass
        
        return history

    def _report(self) -> None:
        # very small report that lists contracts and functions
        from .report.builder import build_report
        build_report(self.outdir)

    def run(self) -> Path:
        self._prepare()
        flows = self._explore()
        journeys = self._journeys(flows)
        self._threats(flows, journeys)
        # load threats from file for gating
        threats = {}
        tfile = self.outdir / 'threats.json'
        if tfile.exists():
            try: threats = __import__("json").loads(tfile.read_text())
            except Exception: threats = {}
        self._generate_tests(flows, journeys, threats)
        self._run_tests()
        if self.risk:
            self._compute_and_save_risk(flows, threats)
            # Generate risk badge if enabled
            if self.badge:
                try:
                    from .badges.svg import render_badge
                    risk_path = self.outdir / "runs" / "risk" / "risk.json"
                    if risk_path.exists():
                        render_badge(risk_path, self.outdir, label="risk")
                except Exception as e:
                    print(f"[warn] badge generation failed: {e}")
            
            # Generate risk trend sparkline if enabled
            if self.trend:
                try:
                    from .trends.sparkline import render_sparkline
                    risk_path = self.outdir / "runs" / "risk" / "risk.json"
                    if risk_path.exists():
                        # Load current risk data
                        risk_data = __import__("json").loads(risk_path.read_text())
                        current_score = float(risk_data.get("summary", {}).get("overall", 0.0))
                        current_grade = str(risk_data.get("summary", {}).get("grade", "Info"))
                        
                        # Load best available history
                        history = self._load_history()
                        
                        # Append current score and cap to trend_n
                        history.append({
                            "ts": datetime.utcnow().isoformat() + "Z",
                            "overall": current_score
                        })
                        history = history[-self.trend_n:]  # Keep last N
                        
                        # Save local history
                        history_path = self.outdir / "runs" / "risk" / "history.json"
                        history_path.parent.mkdir(parents=True, exist_ok=True)
                        history_path.write_text(__import__("json").dumps(history, indent=2))
                        
                        # Generate sparkline
                        scores = [entry["overall"] for entry in history]
                        sparkline_path, data_uri = render_sparkline(scores, current_grade, self.outdir)
                        
                        # Save trend metadata
                        trend_meta = {
                            "count": len(history),
                            "min": min(scores) if scores else 0.0,
                            "max": max(scores) if scores else 0.0,
                            "latest": current_score,
                            "grade": current_grade,
                            "source": "local"
                        }
                        trend_meta_path = self.outdir / "runs" / "risk" / "trend.meta.json"
                        trend_meta_path.write_text(__import__("json").dumps(trend_meta, indent=2))
                        
                except Exception as e:
                    print(f"[warn] trend generation failed: {e}")
        self._report()
        
        # Generate PDF report if enabled
        if self.pdf:
            try:
                from .report.pdf import render_pdf
                html_path = self.outdir / "report.html"
                if html_path.exists():
                    pdf_path = html_path.with_suffix('.pdf')
                    if render_pdf(str(html_path), str(pdf_path), str(self.outdir)):
                        print(f"PDF report generated: {pdf_path}")
                    else:
                        print(f"[warn] PDF generation failed")
            except Exception as e:
                print(f"[warn] PDF generation failed: {e}")
        
        return self.outdir
