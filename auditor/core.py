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
        
        # Initialize LLM policy
        from .llm.policy import create_llm_policy, LLMConfig
        from .llm.engine import detect_provider
        
        # Detect provider and create config
        provider_meta = detect_provider(llm_provider if llm else "off")
        llm_config = LLMConfig(
            enabled=llm and provider_meta.enabled,
            provider=provider_meta.provider,
            model=llm_model or provider_meta.model
        )
        self.llm_policy = create_llm_policy(out_root, llm_config)
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
        # basic JSONL log for step-by-step progress
        self.log_path = self.outdir / "runs" / "orchestrator.log.jsonl"
        # optional status file updated on each log event
        self.status_path: Path | None = self.outdir / "status.json"
        # coarse phase weights to approximate progress
        self._phase_weights = {
            "prepare": 5,
            "inventory": 10,
            "analysis": 15,
            "journey_plan": 15,
            "test_synth": 20,
            "compile_precheck": 10,
            "execute_tests": 10,
            "risk": 8,
            "report": 7,
        }
        self._phase_order = [
            "prepare","inventory","analysis","journey_plan","test_synth","compile_precheck","execute_tests","risk","report"
        ]
        self._current_phase = "prepare"

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
        self._log("prepare", {"input": self.input, "kind": self.kind})
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

    def _inventory(self) -> None:
        """Collect cheap, deterministic repo inventory and write inventory.json."""
        self._log("inventory.start", {"src_dir": str(self.srcdir)})
        root = self.srcdir
        
        # Detect toolchain
        foundry_toml_found = (self.outdir.parent / "foundry.toml").exists() or (root.parent / "foundry.toml").exists()
        hardhat_configs = [p for p in ["hardhat.config.ts","hardhat.config.js","package.json"] if (root.parent / p).exists()]
        
        self._log("inventory.toolchain_detection", {
            "foundry_toml": foundry_toml_found,
            "hardhat_configs": hardhat_configs,
            "src_dir": str(root)
        })
        
        toolchain = {
            "foundry": foundry_toml_found,
            "hardhat": len(hardhat_configs) > 0,
            "remappings": [],
            "solc_versions": []
        }
        # remappings
        for candidate in [root.parent/"remappings.txt", root/"remappings.txt"]:
            if candidate.exists():
                try:
                    toolchain["remappings"] = [ln.strip() for ln in candidate.read_text().splitlines() if ln.strip()]
                    break
                except Exception:
                    pass
        # scan solidity files
        contracts = []
        standards = set()
        sol_files = list(root.rglob("*.sol"))
        
        self._log("inventory.solidity_scan", {
            "total_sol_files": len(sol_files),
            "scanning_limit": min(1000, len(sol_files)),
            "files": [str(f.relative_to(root)) for f in sol_files[:10]]  # Show first 10 files
        })
        
        for sf in sol_files[:1000]:  # cap
            try:
                text = sf.read_text(errors="ignore")
            except Exception:
                text = ""
            name = sf.stem
            inherits = []
            modifiers = []
            events = []
            # very light heuristics
            if "Ownable" in text:
                inherits.append("Ownable")
                standards.add("Ownable")
            if "AccessControl" in text:
                inherits.append("AccessControl")
                standards.add("AccessControl")
            if "ERC20" in text:
                standards.add("ERC20")
            if "ERC721" in text:
                standards.add("ERC721")
            if "ERC1155" in text:
                standards.add("ERC1155")
            # events
            if "event Transfer(" in text:
                events.append("Transfer(...)")
            contracts.append({
                "name": name,
                "inherits": inherits,
                "modifiers": modifiers,
                "functions": [],
                "events": events
            })
        inventory = {
            "toolchain": toolchain,
            "standards": sorted(list(standards)),
            "contracts": contracts,
            "existingTests": [],
            "docSummary": []
        }
        json_dump_atomic(self.outdir / "inventory.json", inventory)

    def _explore(self) -> dict:
        self._log("explore.start", {})
        flows = extract_flows_from_dir(self.srcdir, kind=self.kind)
        # validate and write
        validate_json(flows, Path("auditor/schemas/flows.schema.json"))
        json_dump_atomic(self.outdir / "flows.json", flows)
        return flows

    def _journeys(self, flows: dict) -> dict:
        self._log("journeys.start", {"contracts": len(flows.get("contracts") or [])})
        
        # Load clustering results if available
        from .llm.clustering import load_clusters, cluster_contract_functions, extract_functions_from_flows, extract_modifiers_from_flows, extract_events_from_flows, save_clusters
        from .llm.engine import LLMMeta
        
        clusters = load_clusters(self.outdir)
        if not clusters and self.llm_policy.config.enabled:
            # Generate clusters for the first contract (or could be all contracts)
            contracts = flows.get("contracts", [])
            if contracts:
                contract_name = contracts[0].get("name", "")
                functions = extract_functions_from_flows(flows, contract_name)
                modifiers = extract_modifiers_from_flows(flows, contract_name)
                events = extract_events_from_flows(flows, contract_name)
                
                provider_meta = LLMMeta(
                    enabled=self.llm_policy.config.enabled,
                    provider=self.llm_policy.config.provider,
                    model=self.llm_policy.config.model,
                    reason="policy_enabled"
                )
                
                clusters = cluster_contract_functions(
                    contract_name, functions, modifiers, events,
                    self.llm_policy, provider_meta
                )
                
                if clusters:
                    save_clusters(self.outdir, clusters)
        
        journeys = make_journeys(flows, clusters)
        validate_json(journeys, Path("auditor/schemas/journeys.schema.json"))
        json_dump_atomic(self.outdir / "journeys.json", journeys)
        return journeys

    def _threats(self, flows: dict, journeys: dict) -> dict:
        self._log("slither.start", {
            "src_dir": str(self.srcdir),
            "static_mode": self.static_mode,
            "static_dir": str(self.outdir / "runs" / "static")
        })
        # Run Slither (Docker). Always write something even on failure.
        static_dir = self.outdir / "runs" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
        
        self._log("slither.executing", {
            "command": f"docker run slither on {self.srcdir}",
            "mode": self.static_mode
        })
        
        res = run_slither(self.srcdir, static_dir, mode=self.static_mode)
        
        self._log("slither.result", {
            "success": res.get("ok", False),
            "mode": res.get("mode", "unknown"),
            "path": res.get("path", "none")
        })
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
        journeys_list = journeys.get("journeys") or []
        self._log("tests.start", {
            "journey_count": len(journeys_list),
            "journeys": [j.get("id", "unknown") for j in journeys_list[:5]],  # Show first 5 journey IDs
            "flows_contracts": len(flows.get("contracts", [])),
            "threats_count": len(threats.get("by_function", {}))
        })
        
        # Use LLM policy for cost-aware calls
        from .llm.engine import LLMMeta
        provider_meta = LLMMeta(
            enabled=self.llm_policy.config.enabled,
            provider=self.llm_policy.config.provider,
            model=self.llm_policy.config.model,
            reason="policy_enabled" if self.llm_policy.config.enabled else "policy_disabled"
        )
        
        # persist llm meta
        meta_dir = self.outdir / "runs" / "llm"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta.json").write_text(__import__("json").dumps({
            "enabled": provider_meta.enabled, 
            "provider": provider_meta.provider, 
            "model": provider_meta.model, 
            "reason": provider_meta.reason,
            "usage": self.llm_policy.get_usage_summary()
        }, indent=2))
        
        # build and save ABI map for EVM contracts
        abi_map = self._build_abi_map(flows) if self.kind == "evm" else {}
        if abi_map:
            self._save_abi_map(abi_map)
        
        tests = {"tests": []}
        if self.kind == "evm":
            tests = generate_foundry_tests(flows, journeys, self.srcdir, self.outdir,
                                         threats=threats, eop_mode=self.eop_mode,
                                         llm_meta=provider_meta, abi_map=abi_map, llm_policy=self.llm_policy)
        elif self.kind == "stellar":
            tests = generate_soroban_tests(flows, journeys, self.srcdir, self.outdir)
        # persist test meta (e.g., eop_mode)
        meta_dir = self.outdir / "runs" / "tests"
        meta_dir.mkdir(parents=True, exist_ok=True)
        (meta_dir / "meta.json").write_text(__import__("json").dumps({"eop_mode": self.eop_mode}, indent=2))
        return tests

    def _run_tests(self) -> dict:
        test_root = self.outdir / "tests" / ("evm" if self.kind=="evm" else "soroban")
        runs_dir = self.outdir / "runs" / "tests"
        
        self._log("tests.run.start", {
            "test_root": str(test_root),
            "runs_dir": str(runs_dir),
            "kind": self.kind,
            "test_root_exists": test_root.exists()
        })
        
        results = {"runs": []}
        if test_root.exists():
            projects = [p for p in sorted(test_root.iterdir()) if p.is_dir()]
            self._log("tests.run.projects_found", {
                "project_count": len(projects),
                "projects": [p.name for p in projects[:10]]  # Show first 10 project names
            })
            
            for proj in projects:
                self._log("tests.run.executing_project", {
                    "project": proj.name,
                    "project_path": str(proj)
                })
                
                out_file = runs_dir / f"{proj.name}.json"
                if self.kind == "evm":
                    res = run_forge_tests(proj, out_file)
                else:
                    res = run_cargo_tests(proj, out_file)
                
                self._log("tests.run.project_result", {
                    "project": proj.name,
                    "passed": res.get("passed", 0),
                    "failed": res.get("failed", 0),
                    "exit_code": res.get("exit_code", -1)
                })
                
                results["runs"].append(res)
        else:
            self._log("tests.run.no_projects", {"test_root": str(test_root)})
        # Noise shrink if failures high
        total = sum(1 for r in results.get("runs", []) for _ in r.get("tests", [])) or 0
        failures = sum(1 for r in results.get("runs", []) for t in r.get("tests", []) if t.get("status") == "failed")
        if total > 0 and (failures/total) > 0.3:
            for r in results.get("runs", []):
                first_fail_kept = False
                compact = []
                for t in r.get("tests", []):
                    if t.get("status") == "passed":
                        compact.append(t)
                    elif not first_fail_kept:
                        compact.append(t)
                        first_fail_kept = True
                r["tests"] = compact
                r["note"] = "compact_view"
        self._log("tests.run.end", {"runs": len(results.get("runs", []))})
        return results

    def _compute_and_save_risk(self, flows, threats):
        self._log("risk.start", {})
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
        self._log("report.start", {
            "outdir": str(self.outdir),
            "report_files": ["report.html", "report.pdf", "report.md"]
        })
        # very small report that lists contracts and functions
        from .report.builder import build_report
        
        self._log("report.building", {"builder": "build_report"})
        build_report(self.outdir)
        
        # Check what files were generated
        report_files = []
        for ext in ["html", "pdf", "md"]:
            report_file = self.outdir / f"report.{ext}"
            if report_file.exists():
                report_files.append(f"report.{ext}")
        
        self._log("report.completed", {
            "generated_files": report_files,
            "outdir": str(self.outdir)
        })

    def run(self) -> Path:
        self._log("run.start", {
            "outdir": str(self.outdir),
            "input": self.input,
            "kind": self.kind,
            "llm_enabled": self.llm,
            "static_mode": self.static_mode,
            "risk_enabled": self.risk,
            "pdf_enabled": self.pdf
        })
        
        self._log("run.phase", {"phase": "prepare", "description": "Setting up workspace and cloning sources"})
        self._prepare()
        
        self._log("run.phase", {"phase": "inventory", "description": "Detecting toolchain and scanning contracts"})
        self._inventory()
        
        self._log("run.phase", {"phase": "explore", "description": "Extracting contract flows and functions"})
        flows = self._explore()
        
        self._log("run.phase", {"phase": "journeys", "description": "Planning test journeys and scenarios"})
        journeys = self._journeys(flows)
        
        self._log("run.phase", {"phase": "threats", "description": "Running static analysis with Slither"})
        self._threats(flows, journeys)
        
        # load threats from file for gating
        threats = {}
        tfile = self.outdir / 'threats.json'
        if tfile.exists():
            try: threats = __import__("json").loads(tfile.read_text())
            except Exception: threats = {}
        
        self._log("run.phase", {"phase": "test_generation", "description": "Generating Foundry test projects"})
        self._generate_tests(flows, journeys, threats)
        
        self._log("run.phase", {"phase": "test_execution", "description": "Running generated tests"})
        self._run_tests()
        if self.risk:
            self._log("run.phase", {"phase": "risk_scoring", "description": "Computing risk scores and analysis"})
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
                from .report.pdf import render_standard_pdf
                pdf_data = {
                    "title": "Uatu Audit Report",
                    "report_kind": "Smart Contract Security Analysis",
                    "contract_id": "Unknown",  # Could be extracted from flows
                    "commit": "N/A",
                    "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "summary": {},
                    "risk_top": [],
                    "risk_heatmap": [],
                    "tests": {"passed": 0, "total": 0, "journeys": 0},
                    "eop": {"total": 0, "covered": 0},
                    "llm": {"status": "disabled"},
                    "static": {"status": "ok", "findings": 0},
                    "gas": {"top_fn": "-", "top_val": "-"},
                    "findings": [],
                    "sparkline_data_uri": "",
                    "versions": {"tool": "UatuAudit v2.0"},
                    "modes": "Standard",
                    "year": __import__("datetime").datetime.now().year
                }
                pdf_path = self.outdir / "report.pdf"
                if render_standard_pdf(pdf_data, pdf_path, self.outdir):
                    print(f"PDF report generated: {pdf_path}")
                else:
                    print(f"[warn] PDF generation failed")
            except Exception as e:
                print(f"[warn] PDF generation failed: {e}")
        
        self._log("run.end", {"outdir": str(self.outdir)})
        return self.outdir

    def _log(self, event: str, data: dict) -> None:
        try:
            import json, time
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            rec = {"ts": datetime.utcnow().isoformat()+"Z", "event": event, **(data or {})}
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(rec) + "\n")
            # Also print to console for immediate visibility
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {event}: {json.dumps(data, indent=2) if data else 'No data'}")
            # try to update coarse status progress
            self._update_status(event, data)
        except Exception as e:
            print(f"Logging error: {e}")
            pass

    def _update_status(self, event: str, data: dict) -> None:
        try:
            if not self.status_path:
                return
            # map events to phases
            event_to_phase = {
                "run.start": "prepare",
                "prepare": "prepare",
                "inventory.start": "inventory",
                "explore.start": "inventory",
                "slither.start": "analysis",
                "journeys.start": "journey_plan",
                "tests.start": "test_synth",
                "tests.run.start": "execute_tests",
                "risk.start": "risk",
                "report.start": "report",
                "run.end": "report",
            }
            phase = event_to_phase.get(event, self._current_phase)
            self._current_phase = phase
            # compute pct: sum of completed phase weights; simple heuristic for in-phase fraction
            completed = 0
            for p in self._phase_order:
                if p == phase:
                    break
                completed += self._phase_weights.get(p, 0)
            in_phase = 0
            # basic in-phase fraction based on hints
            if phase == "test_synth":
                total = max(1, int((data or {}).get("journey_count", 0)))
                done = int((data or {}).get("journeys_done", 0))
                in_phase = min(0.99, done/total) if total else 0
            elif phase == "execute_tests":
                total = max(1, int((data or {}).get("runs", 0)))
                done = int((data or {}).get("done", 0))
                in_phase = min(0.99, done/total) if total else 0
            pct = min(100, int(round(completed + self._phase_weights.get(phase,0)*in_phase)))
            status = {
                "phase": phase,
                "pct": pct,
                "updated_at": datetime.utcnow().isoformat()+"Z",
            }
            self.status_path.write_text(__import__("json").dumps(status, indent=2))
        except Exception:
            pass
