from __future__ import annotations
import subprocess, json
from pathlib import Path
from typing import Dict, Any

def run_cargo_tests(project_dir: Path, out_json: Path) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            ["cargo", "test", "--quiet"],
            cwd=str(project_dir),
            capture_output=True, text=True, timeout=1200
        )
        # Best-effort parse: treat exit_code 0 as all passed (we don't enumerate unit names)
        res = {
            "project": project_dir.name,
            "passed": 0 if proc.returncode != 0 else 1,
            "failed": 0 if proc.returncode == 0 else 1,
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "stderr_tail": (proc.stderr or "")[-1500:]
        }
    except Exception as e:
        res = {"project": project_dir.name, "passed": 0, "failed": 0, "exit_code": -1, "error": str(e)}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(res, indent=2))
    return res
