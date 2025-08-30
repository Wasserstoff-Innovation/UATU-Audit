from __future__ import annotations
import re, json, os, shutil
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from jsonschema import validate, Draft202012Validator

ADDR_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

def is_eth_address(s: str) -> bool:
    return bool(ADDR_RE.match(s))

def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data)
    tmp.replace(path)

def json_dump_atomic(path: Path, obj: Any) -> None:
    atomic_write(path, json.dumps(obj, indent=2))

def validate_json(obj: Any, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    validate(instance=obj, schema=schema)

def copy_source_to_work(src: str, work_src: Path) -> None:
    work_src.mkdir(parents=True, exist_ok=True)
    p = Path(src)
    if p.is_file():
        shutil.copy2(p, work_src / p.name)
    elif p.is_dir():
        shutil.copytree(p, work_src, dirs_exist_ok=True)
    else:
        raise FileNotFoundError(f"Input path not found: {src}")

def etherscan_fetch_sources(address: str, api_key: Optional[str], dest_dir: Path) -> Dict[str, Any]:
    """Fetch verified source from Etherscan and write files under dest_dir/sources/*"""
    if not api_key:
        raise ValueError("ETHERSCAN_API_KEY is required to fetch sources by address.")
    url = f"https://api.etherscan.io/api"
    params = {"module":"contract","action":"getsourcecode","address":address,"apikey":api_key}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "1" or not data.get("result"):
        raise RuntimeError(f"Etherscan error: {data.get('message')}")
    item = data["result"][0]
    src_raw = item.get("SourceCode") or ""
    name = item.get("ContractName") or address
    out_root = dest_dir / "sources"
    out_root.mkdir(parents=True, exist_ok=True)

    # Try parse multi-file JSON first
    written = []
    parsed = None
    s = src_raw.strip()
    # Etherscan sometimes wraps JSON in extra quotes/braces; try a few heuristics
    for candidate in (s, s.strip("{}"), s.strip('"')):
        try:
            parsed = json.loads(candidate)
            break
        except Exception:
            parsed = None

    if isinstance(parsed, dict):
        # common shapes: {"sources": {"path.sol":{"content":"..."}}, ...} OR {"path.sol":"content", ...}
        sources = parsed.get("sources", parsed)
        for path, val in sources.items():
            if isinstance(val, dict) and "content" in val:
                code = val["content"]
            else:
                code = str(val)
            out_path = out_root / path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(code)
            written.append(str(out_path))
    else:
        # single-file
        (out_root / f"{name}.sol").write_text(src_raw)
        written.append(str(out_root / f"{name}.sol"))

    meta = {
        "contractName": name,
        "compilerVersion": item.get("CompilerVersion"),
        "files": written
    }
    (dest_dir / "meta.etherscan.json").write_text(json.dumps(meta, indent=2))
    return meta
