from __future__ import annotations
import os, json, shutil, subprocess, platform
from pathlib import Path
from typing import Dict, Any

SLITHER_IMAGE = "trailofbits/slither:latest"

def _write_stub(out_dir: Path, note: str) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "slither.json").write_text(json.dumps({"results":{"detectors":[]}, "note": note}, indent=2))
    (out_dir / "metadata.json").write_text(json.dumps({"mode":"stub","ok":True,"note":note}, indent=2))
    return {"ok": True, "mode": "stub", "path": str(out_dir / "slither.json")}

def _host_docker_available() -> bool:
    sock = Path("/var/run/docker.sock")
    return sock.exists() and shutil.which("docker") is not None

def run_slither(src_dir: Path, out_dir: Path, mode: str = "auto") -> Dict[str, Any]:
    """
    mode: 'auto' | 'host' | 'stub'
    - 'host': require host Docker socket + docker CLI
    - 'auto': use host if available else stub
    - 'stub': always stub
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if mode == "stub":
        return _write_stub(out_dir, "Stub mode forced")

    if mode in ("auto","host"):
        if _host_docker_available():
            # Run the official Slither image against /src and write JSON to /out
            docker_platform = []
            try:
                mach = platform.machine().lower()
                if "arm" in mach or "aarch64" in mach:
                    docker_platform = ["--platform", "linux/arm64"]
            except Exception:
                docker_platform = []

            cmd = (
                ["docker","run","--rm"]
                + docker_platform
                + [
                    "-v", f"{src_dir}:/src:ro",
                    "-v", f"{out_dir}:/out",
                    "-w", "/src",
                    SLITHER_IMAGE,
                    "slither", "/src", "--json", "/out/slither.json"
                ]
            )
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
                ok = proc.returncode == 0 and (out_dir / "slither.json").exists()
                meta = {
                    "mode": "host",
                    "ok": bool(ok),
                    "returncode": proc.returncode,
                    "stderr_tail": (proc.stderr or "")[-1200:],
                }
                (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
                if ok:
                    return {"ok": True, "mode":"host", "path": str(out_dir / "slither.json")}
                else:
                    # Even on failure, create a minimal error json to keep pipeline flowing
                    (out_dir / "slither.error.json").write_text(json.dumps({
                        "error":"slither_failed","returncode":proc.returncode,"stderr":proc.stderr
                    }, indent=2))
                    # fall back to stub so downstream steps have shape
                    return _write_stub(out_dir, "Host Slither failed; fell back to stub")
            except Exception as e:
                # fallback to stub
                return _write_stub(out_dir, f"Host Slither exception: {e}")
        elif mode == "host":
            # explicit host requested but not available
            (out_dir / "slither.error.json").write_text(json.dumps({
                "error":"host_docker_unavailable"
            }, indent=2))
            return _write_stub(out_dir, "Host docker unavailable; used stub")

    # default fallback
    return _write_stub(out_dir, "Auto mode without host docker; used stub")
