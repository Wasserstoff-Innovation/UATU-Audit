from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import shutil, json, re

def _default_rust_arg(ty: str) -> str:
    t = (ty or "").replace("&", "").strip()
    if t in ("u8","u16","u32","u64","u128","usize","i8","i16","i32","i64","i128","isize"): return "1"
    if t.startswith("Option<"): return "None"
    if t == "bool": return "true"
    if t.startswith("Vec<"): return "Vec::new()"
    if t == "String" or t == "&str": return 'String::from("")'
    return "Default::default()"

def _camel(id_: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", " ", id_).title().replace(" ", "")
    return base

def generate_soroban_tests(flows: Dict[str,Any], journeys: Dict[str,Any], work_src: Path, outdir: Path) -> Dict[str,Any]:
    root = outdir / "tests" / "soroban"
    idx = {"tests": []}
    for j in journeys.get("journeys", []):
        jid = j["id"]; steps = j.get("steps", [])
        if not steps: continue
        # Assume first step's contract is the module name
        module = steps[0]["contract"]
        proj = root / jid
        (proj / "src").mkdir(parents=True, exist_ok=True)
        (proj / "tests").mkdir(parents=True, exist_ok=True)
        # copy all .rs sources into src
        if work_src.exists():
            for f in work_src.rglob("*.rs"):
                rel = f.relative_to(work_src)
                dst = proj / "src" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dst)
        # cargo manifest
        (proj / "Cargo.toml").write_text(f"""[package]
name = "soro_{jid.replace('-', '_')}"
version = "0.1.0"
edition = "2021"

[lib]
name = "lib_{jid.replace('-', '_')}"
path = "src/lib.rs"

[dev-dependencies]
""")
        # single integration test file invoking functions at module::<fn>(args)
        calls = []
        for st in steps:
            fn = st["function"]
            # find signature in flows for arg types
            types = []
            for c in flows.get("contracts", []):
                if c["name"] == module:
                    meta = next((f for f in c.get("functions", []) if f["name"] == fn), None)
                    if meta:
                        types = [i.get("type","") for i in meta.get("inputs",[])]
                        break
            args = ", ".join(_default_rust_arg(t) for t in types)
            calls.append(f"    let _ = {module}::{fn}({args});")
        test_code = "\n".join(calls) if calls else "    // no-op"
        (proj / "tests" / "generated.rs").write_text(f"""use lib_{jid.replace('-', '_')}::{module};

#[test]
fn journey_compiles_and_runs() {{
{test_code}
}}
""")
        idx["tests"].append({"id": f"{jid}_generated", "journey_id": jid, "tool": "cargo"})
    (outdir / "tests_rust.json").write_text(json.dumps(idx, indent=2))
    return idx
