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

class Orchestrator:
    def __init__(self, input_path_or_address: str, kind: str = "evm", out_root: Path = Path("out"), llm: bool = False, static_mode: str = "auto"):
        self.input = input_path_or_address
        self.kind = kind
        self.out_root = out_root
        self.llm = llm
        self.static_mode = static_mode

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.outdir = out_root / ts
        self.workdir = self.outdir / "work"
        self.srcdir = self.workdir / "src"
        (self.outdir / "runs").mkdir(parents=True, exist_ok=True)

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

    def _generate_tests(self, flows: dict, journeys: dict) -> dict:
        tests = {"tests": []}
        if self.kind == "evm":
            tests = generate_foundry_tests(flows, journeys, self.srcdir, self.outdir)
        elif self.kind == "stellar":
            tests = generate_soroban_tests(flows, journeys, self.srcdir, self.outdir)
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

    def _report(self) -> None:
        # very small report that lists contracts and functions
        from .report.builder import build_report
        build_report(self.outdir)

    def run(self) -> Path:
        self._prepare()
        flows = self._explore()
        journeys = self._journeys(flows)
        self._threats(flows, journeys)
        self._generate_tests(flows, journeys)
        self._run_tests()
        self._report()
        return self.outdir
