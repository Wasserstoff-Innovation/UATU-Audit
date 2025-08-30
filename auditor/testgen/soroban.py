from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import shutil, json, re

def _default_rust_arg(ty: str) -> str:
    t = (ty or "").replace("&", "").strip()
    # Soroban common types
    if t.endswith('Env') or t.endswith('soroban_sdk::Env') or t == 'Env': return 'Env::default()'  # not used as arg when using client
    if t.endswith('Address') or t == 'Address': return 'TestAddress::generate(&e)'
    if t.endswith('Symbol') or t == 'Symbol': return 'Symbol::new(&e, "sym")'
    if t.endswith('Bytes') or t.startswith('BytesN'): return 'Bytes::new(&e)'
    if t in ('i128',): return '1_i128'
    if t in ('i64','i32','i16','i8'): return '&1'  # Soroban expects references
    # fall through to existing defaults below
    if t in ("u8","u16","u32","u64","u128","usize","i8","i16","i32","i64","i128","isize"): return "&1"  # Soroban expects references
    if t.startswith("Option<"): return "None"
    if t == "bool": return "true"
    if t.startswith("Vec<"): return "Vec::new()"
    if t == "String" or t == "&str": return 'String::from("")'
    return "Default::default()"

def _camel(id_: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", " ", id_).title().replace(" ", "")
    return base

def _find_soroban_contract(flows: Dict[str,Any], steps: List[Dict[str,Any]]) -> Tuple[str,str] | None:
    # returns (ContractTypeName, ClientTypeName) if markers present; else None
    contract = steps[0]["contract"]
    # contract type name equals contract struct name in flows when extracted by soroban parser
    # Client name is <Contract>Client by soroban-sdk macro
    # We assume if flows contains `contract` with functions and examples compile with Env, it's Soroban-ish.
    c = next((c for c in (flows.get("contracts") or []) if c.get("name")==contract), None)
    if not c:
        return None
    # Soroban detection: if any function input type looks like Address/Symbol/i128 (typical)
    fns = c.get("functions") or []
    if any(any((i.get("type","")).endswith(x) or i.get("type","")==x for x in ("Address","Symbol","i128","Env","soroban_sdk::Env")) for fn in fns for i in fn.get("inputs",[])):
        return (contract, f"{contract}Client")
    return None

def generate_soroban_tests(flows: Dict[str,Any], journeys: Dict[str,Any], work_src: Path, outdir: Path) -> Dict[str,Any]:
    root = outdir / "tests" / "soroban"
    idx = {"tests": []}
    for j in journeys.get("journeys", []):
        jid = j["id"]; steps = j.get("steps", [])
        if not steps: continue
        module = steps[0]["contract"]
        proj = root / jid
        (proj / "src").mkdir(parents=True, exist_ok=True)
        (proj / "tests").mkdir(parents=True, exist_ok=True)
        # copy sources
        if work_src.exists():
            for f in work_src.rglob("*.rs"):
                rel = f.relative_to(work_src)
                dst = proj / "src" / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dst)

        # Soroban-aware manifest with dev-deps
        (proj / "Cargo.toml").write_text(f"""[package]
name = "soro_{jid.replace('-', '_')}"
version = "0.1.0"
edition = "2021"

[lib]
name = "lib_{jid.replace('-', '_')}"
path = "src/lib.rs"

[dependencies]
soroban-sdk = {{ version = "21.0.0", features = ["alloc"] }}

[dev-dependencies]
soroban-sdk = {{ version = "21.0.0", features = ["testutils"] }}
""")

        # Determine Soroban vs fallback
        soroban_pair = _find_soroban_contract(flows, steps)

        if soroban_pair:
            contract_type, client_type = soroban_pair
            calls = []
            for st in steps:
                fn = st["function"]
                # types for args (excluding Env)
                types = []
                for c in flows.get("contracts", []):
                    if c["name"] == module:
                        meta = next((f for f in c.get("functions", []) if f["name"] == fn), None)
                        if meta:
                            types = [i.get("type","") for i in meta.get("inputs",[])]
                            break
                # build args using e-bound defaults (Env available as `e`)
                # NOTE: we don't pass Env when using client
                filtered = [t for t in types if t not in ("Env","soroban_sdk::Env")]
                args = ", ".join(_default_rust_arg(t) for t in filtered)
                calls.append(f"    let _ = client.{fn}({args});")
            body = "\n".join(calls) if calls else "    // no-op"
            (proj / "tests" / "generated.rs").write_text(f"""use soroban_sdk::{{testutils::*, Env, Address, Symbol, Bytes}};
use soroban_sdk::testutils::Address as TestAddress;
use lib_{jid.replace('-', '_')}::*;

#[test]
fn journey_with_env_and_client() {{
    let e = Env::default();
    let addr = e.register_contract(None, {contract_type});
    let client = {client_type}::new(&e, &addr);
{body}
}}
""")
        else:
            # fallback to plain Rust module calls
            calls = []
            for st in steps:
                fn = st["function"]
                types = []
                for c in flows.get("contracts", []):
                    if c["name"] == module:
                        meta = next((f for f in c.get("functions", []) if f["name"] == fn), None)
                        if meta:
                            types = [i.get("type","") for i in meta.get("inputs",[])]
                            break
                args = ", ".join(_default_rust_arg(t) for t in types)
                calls.append(f"    let _ = {module}::{fn}({args});")
            body = "\n".join(calls) if calls else "    // no-op"
            (proj / "tests" / "generated.rs").write_text(f"""#[test]
fn journey_compiles_and_runs() {{
{body}
}}
""")

        idx["tests"].append({ "id": f"{jid}_generated", "journey_id": jid, "tool": "cargo" })
    (outdir / "tests_rust.json").write_text(json.dumps(idx, indent=2))
    return idx
