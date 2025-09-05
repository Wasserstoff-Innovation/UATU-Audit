from __future__ import annotations
import subprocess, json, re
from pathlib import Path
from typing import Dict, Any

def forge_build(project_dir: Path, timeout: int = 180) -> tuple[int, str, str]:
    """Run 'forge build' in the given project dir. Returns (code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["forge", "build"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as e:
        return 99, "", f"forge build exception: {e}"

SUMMARY_RE = re.compile(r"(\d+)\s+passed;\s+(\d+)\s+failed", re.I)
PASS_RE = re.compile(r"\[PASS\]\s+(test\w+)\b")
FAIL_RE = re.compile(r"\[FAIL\]\s+(test\w+)\b")
SNAP_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\(\)\s*\(gas:\s*(\d+)\)\s*$")

def _run(cmd, cwd: Path) -> tuple[int,str,str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or ""), (p.stderr or "")

def run_forge_tests(project_dir: Path, out_json: Path) -> Dict[str, Any]:
    try:
        # Install OpenZeppelin dependencies if needed
        lib_dir = project_dir / "lib"
        lib_dir.mkdir(exist_ok=True)
        
        oz_dir = lib_dir / "openzeppelin-contracts"
        if not oz_dir.exists():
            # Initialize git repo if not exists (required for forge install)
            if not (project_dir / ".git").exists():
                _run(["git", "init"], project_dir)
            
            # Clone OpenZeppelin contracts directly
            _run(["git", "clone", "--depth", "1", "https://github.com/OpenZeppelin/openzeppelin-contracts.git", str(oz_dir)], project_dir)
        
        # First try to build to check for compilation errors
        build_code, build_out, build_err = forge_build(project_dir)
        if build_code != 0:
            # Compilation failed - report as error
            res = {
                "project": project_dir.name,
                "passed": 0,
                "failed": 1,
                "exit_code": build_code,
                "tests": [],
                "gas": {},
                "error": f"Compilation failed: {(build_err or build_out)[-2000:]}",
                "status": "compile_error"
            }
        else:
            # Compilation succeeded, run tests
            code, out, err = _run(["forge", "test", "-vv"], project_dir)
            passed = failed = 0
            m = SUMMARY_RE.search(out)
            if m:
                passed, failed = int(m.group(1)), int(m.group(2))
            tests = []
            for name in PASS_RE.findall(out):
                tests.append({"name": name, "status": "passed"})
            for name in FAIL_RE.findall(out):
                tests.append({"name": name, "status": "failed"})
            # Gas snapshot (best-effort)
            _run(["forge", "snapshot"], project_dir)
            gas = {}
            snap = project_dir / ".gas-snapshot"
            if snap.exists():
                for line in snap.read_text().splitlines():
                    m = SNAP_RE.match(line.strip())
                    if m:
                        gas[m.group(1)] = int(m.group(2))
            res = {
                "project": project_dir.name,
                "passed": passed,
                "failed": failed,
                "exit_code": code,
                "tests": tests,
                "gas": gas,
                "status": "tests_run" if tests else "no_tests"
            }
            if code != 0 and not tests and passed == 0 and failed == 0:
                # Attach a concise error hint to help the report/UI
                res["error"] = (err or out)[-2000:]
                res["status"] = "test_error"
    except Exception as e:
        res = {"project": project_dir.name, "passed": 0, "failed": 1, "exit_code": -1, "error": str(e), "tests": [], "gas": {}, "status": "exception"}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(res, indent=2))
    return res
