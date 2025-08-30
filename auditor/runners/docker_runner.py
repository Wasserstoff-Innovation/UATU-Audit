import subprocess
from typing import List, Tuple, Dict

def run(image: str, args: List[str], mounts: List[Tuple[str,str]] = [], env: Dict[str,str] = None, workdir: str = None, timeout: int = 600):
    cmd = ["docker","run","--rm"]
    # Mount the host Docker socket to enable Docker-in-Docker
    cmd += ["-v", "/var/run/docker.sock:/var/run/docker.sock"]
    for h,c in mounts:
        cmd += ["-v", f"{h}:{c}"]
    if env:
        for k,v in env.items():
            cmd += ["-e", f"{k}={v}"]
    if workdir:
        cmd += ["-w", workdir]
    cmd += [image] + args
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
