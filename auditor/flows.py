from __future__ import annotations
import re, json
from pathlib import Path
from typing import Dict, Any, List

CONTRACT_RE = re.compile(r"\bcontract\s+(\w+)", re.MULTILINE)
EVENT_RE    = re.compile(r"\bevent\s+(\w+)\s*\(([^)]*)\)\s*;", re.MULTILINE)
FUNC_RE     = re.compile(
    r"function\s+(?P<name>\w+)\s*\((?P<args>[^)]*)\)\s*"
    r"(?P<visibility>public|external|internal|private)?\s*"
    r"(?P<mutability>payable|view|pure|nonpayable)?",
    re.MULTILINE,
)

def _parse_params(argstr: str) -> List[Dict[str, str]]:
    args = []
    for raw in [a.strip() for a in argstr.split(",") if a.strip()]:
        parts = raw.split()
        if len(parts) == 1:
            _type, _name = parts[0], ""
        else:
            _type, _name = " ".join(parts[:-1]), parts[-1]
        # remove memory/storage/calldata/returns noise
        _type = _type.replace("memory","").replace("calldata","").replace("storage","").strip()
        args.append({"name": _name.strip().lstrip("_"), "type": _type.strip()})
    return args

def extract_flows_from_dir(src_dir: Path, kind: str = "evm") -> Dict[str, Any]:
    contracts = []
    for f in src_dir.rglob("*.sol"):
        text = f.read_text(errors="ignore")
        # For each contract in this file
        for m in CONTRACT_RE.finditer(text):
            cname = m.group(1)
            body = text  # naive: scan file-level for funcs/events
            events = []
            for em in EVENT_RE.finditer(body):
                ename, eargs = em.group(1), em.group(2)
                events.append({"name": ename, "params": [a.strip() for a in eargs.split(",") if a.strip()]})

            functions = []
            for fm in FUNC_RE.finditer(body):
                name = fm.group("name")
                inputs = _parse_params(fm.group("args") or "")
                vis = fm.group("visibility") or None
                mut = fm.group("mutability") or None
                # crude heuristic to guess outputs: look for "returns (...)" next to the signature
                # not perfect, but good enough for Task 2
                # (skip for now; leave empty)
                outputs = []
                functions.append({
                    "name": name,
                    "visibility": vis,
                    "mutability": mut,
                    "inputs": inputs,
                    "outputs": outputs,
                    "modifiers": [],
                    "events_emitted": []
                })

            contracts.append({
                "name": cname,
                "visibility": "public",
                "inherits": [],
                "state_vars": [],
                "functions": functions,
                "events": events
            })
    return {"contracts": contracts}

def _extract_evm_flows(root: Path) -> dict:
    contracts = []
    for f in root.rglob("*.sol"):
        text = f.read_text(errors="ignore")
        # For each contract in this file
        for m in CONTRACT_RE.finditer(text):
            cname = m.group(1)
            body = text  # naive: scan file-level for funcs/events
            events = []
            for em in EVENT_RE.finditer(body):
                ename, eargs = em.group(1), em.group(2)
                events.append({"name": ename, "params": [a.strip() for a in eargs.split(",") if a.strip()]})

            functions = []
            for fm in FUNC_RE.finditer(body):
                name = fm.group("name")
                inputs = _parse_params(fm.group("args") or "")
                vis = fm.group("visibility") or None
                mut = fm.group("mutability") or None
                # crude heuristic to guess outputs: look for "returns (...)" next to the signature
                # not perfect, but good enough for Task 2
                # (skip for now; leave empty)
                outputs = []
                functions.append({
                    "name": name,
                    "visibility": vis,
                    "mutability": mut,
                    "inputs": inputs,
                    "outputs": outputs,
                    "modifiers": [],
                    "events_emitted": []
                })

            contracts.append({
                "name": cname,
                "visibility": "public",
                "inherits": [],
                "state_vars": [],
                "functions": functions,
                "events": events
            })
    return {"contracts": contracts}

def _extract_rust_flows(root: Path) -> dict:
    # Very lightweight parser:
    # - treat each 'mod <name> {' as a contract/module
    # - collect 'pub fn <name>(args...)' signatures
    contracts = []
    rs_files = list(root.rglob("*.rs"))
    for f in rs_files:
        try:
            txt = f.read_text(errors="ignore")
        except Exception:
            continue
        # modules as "contracts"
        modules = re.findall(r"\bmod\s+([A-Za-z0-9_]+)\s*\{", txt)
        if not modules:
            # fallback single contract from file stem
            modules = [f.stem]
        for m in modules:
            functions = []
            for mfun in re.finditer(r"\bpub\s+fn\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", txt):
                name = mfun.group(1)
                args = mfun.group(2).strip()
                inputs = []
                if args:
                    for part in [a.strip() for a in args.split(",") if a.strip()]:
                        if ":" in part:
                            nm, ty = [x.strip() for x in part.split(":",1)]
                        else:
                            nm, ty = part, "Unknown"
                        inputs.append({"name": nm, "type": ty})
                functions.append({
                    "name": name,
                    "visibility": "public",
                    "mutability": None,
                    "inputs": inputs,
                    "outputs": []
                })
            if functions:
                contracts.append({
                    "name": m,
                    "events": [],
                    "functions": functions
                })
    return {"contracts": contracts}

def _extract_soroban_flows(root: Path) -> dict:
    # Heuristics for Soroban:
    # - #[contract] pub struct Name;
    # - #[contractimpl] impl Name { pub fn foo(env: Env, ...) ... }
    contracts = []
    for f in root.rglob("*.rs"):
        try:
            txt = f.read_text(errors="ignore")
        except Exception:
            continue
        # find contract structs
        for m in re.finditer(r"#\[contract\]\s*pub\s+struct\s+([A-Za-z0-9_]+)", txt):
            cname = m.group(1)
            functions = []
            # scan impl blocks annotated with #[contractimpl] for this contract
            impl_pat = re.compile(rf"#\[contractimpl\]\s*impl\s+{cname}\s*\{{(.*?)\}}", re.S)
            for iblk in impl_pat.findall(txt):
                for fnm in re.finditer(r"\bpub\s+fn\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)", iblk):
                    fname = fnm.group(1)
                    args = [a.strip() for a in fnm.group(2).split(",") if a.strip()]
                    inputs = []
                    for a in args:
                        if ":" in a:
                            nm, ty = [x.strip() for x in a.split(":",1)]
                        else:
                            nm, ty = a, "Unknown"
                        # drop the Env param from inputs to better match client call signatures
                        if ty.endswith("Env") or ty.endswith("soroban_sdk::Env") or ty == "Env":
                            continue
                        inputs.append({"name": nm, "type": ty})
                    functions.append({"name": fname, "visibility":"public", "mutability":None, "inputs":inputs, "outputs":[]})
            if functions:
                contracts.append({"name": cname, "events": [], "functions": functions})
    # fallback to generic rust if none found
    if not contracts:
        return _extract_rust_flows(root)
    return {"contracts": contracts}

# Update the main function to route based on kind
def extract_flows_from_dir(src_dir: Path, kind: str = "evm") -> Dict[str, Any]:
    if kind == "evm":
        return _extract_evm_flows(src_dir)
    elif kind == "stellar":
        return _extract_soroban_flows(src_dir)
    else:
        # fallback to EVM for unknown kinds
        return _extract_evm_flows(src_dir)
