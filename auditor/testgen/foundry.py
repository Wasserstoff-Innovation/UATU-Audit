from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import shutil, re, json

SENSITIVE_PREFIXES = [
    'withdraw','sweep','rescue','mint','burn','pause','unpause',
    'upgrade','authorize','deauthorize','grantRole','revokeRole',
    'setOwner','transferOwnership','setAdmin','setGuardian','emergency',
    'setFee','setTreasury','setWhitelist','addWhitelist','removeWhitelist'
]

def _is_sensitive_fn(fn: str) -> bool:
    fl = (fn or '').lower()
    return any(fl == p.lower() or fl.startswith(p.lower()) for p in SENSITIVE_PREFIXES)

def _default_arg(sol_type: str) -> str:
    t = (sol_type or "").strip()
    if t.endswith("[]"):
        base = t[:-2].strip() or "uint256"
        return f"new {base}"
    if t.startswith("uint") or t.startswith("int"):
        return "1"
    if t == "address":
        return "address(this)"
    if t == "bool":
        return "true"
    if t.startswith("bytes") and t != "bytes":
        return f"{t}(0)"
    if t == "bytes":
        return 'bytes("")'
    if t == "string":
        return '""'
    return "0"

def _neg_arg(sol_type: str) -> str:
    t = (sol_type or "").strip()
    if t.startswith("uint"):
        return f"type({t}).max" if t != "uint" else "type(uint256).max"
    if t.startswith("int"):
        return f"type({t}).min" if t != "int" else "type(int256).min"
    if t == "address":
        return "address(0)"
    if t == "bool":
        return "false"
    if t.endswith("[]"):
        base = t[:-2].strip() or "uint256"
        return f"new {base}"
    if t.startswith("bytes"):
        return f"{t}(0)" if t != "bytes" else 'bytes("")'
    if t == "string":
        return '""'
    return "0"

def _types_and_args_for_fn(contract_meta: Dict[str,Any], fn_name: str):
    typs, pos_args, neg_args = [], [], []
    meta = next((f for f in contract_meta.get("functions", []) if f["name"] == fn_name), None)
    if meta:
        for i in meta.get("inputs", []):
            t = i.get("type","")
            typs.append(t)
            pos_args.append(_default_arg(t))
            neg_args.append(_neg_arg(t))
    return typs, pos_args, neg_args

def _find_contract_file(src_dir: Path, contract_name: str) -> Optional[Path]:
    pat = re.compile(rf"\bcontract\s+{re.escape(contract_name)}\b")
    for f in src_dir.rglob("*.sol"):
        try:
            if pat.search(f.read_text(errors="ignore")):
                return f
        except Exception:
            pass
    return None

def _test_contract_name(journey_id: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", " ", journey_id).title().replace(" ", "")
    return f"Test{base}"

ATTACKER_SNIPPET = '''
// helper that invokes target via low-level call and returns success flag
contract Attacker {
    address public target;
    constructor(address t){ target = t; }
    function attack(bytes memory data) public returns (bool) {
        (bool ok,) = target.call(data);
        return ok;
    }
}
''';

def _make_test_code(contract_file_rel: str, contract_name: str, steps: List[Dict[str, Any]], flows: Dict[str,Any]) -> str:
    # collect unique function names used in the journey
    uniq_fns = []
    for st in steps:
        fn = st["function"]
        if fn not in uniq_fns:
            uniq_fns.append(fn)

    # primary happy body (high-level calls)
    happy_calls = []
    for st in steps:
        fn = st["function"]
        # inputs for happy path
        contract_meta = next((c for c in flows.get("contracts", []) if c["name"] == contract_name), None) or {}
        _, pos_args, _ = _types_and_args_for_fn(contract_meta, fn)
        arglist = ", ".join(pos_args) if pos_args else ""
        happy_calls.append(f"        s.{fn}({arglist});")
    happy_body = "\n".join(happy_calls) if happy_calls else "        // no-op"

    # negative & stress per unique function
    neg_tests = []
    stress_tests = []
    contract_meta = next((c for c in flows.get("contracts", []) if c["name"] == contract_name), None) or {}
    for fn in uniq_fns:
        types, pos_args, neg_args = _types_and_args_for_fn(contract_meta, fn)
        # signature string for low-level call
        sig = f'{fn}({",".join(types)})'
        neg_arglist = ", ".join(neg_args) if neg_args else ""
        neg_tests.append(f"""
    function test_negative_{fn}() public {{
        {contract_name} s = new {contract_name}();
        // Low-level call to avoid reverting the whole test if function reverts.
        (bool ok, ) = address(s).call(abi.encodeWithSignature("{sig}"{", " if neg_arglist else ""}{neg_arglist}));
        // Intentionally no assert: scaffold that never fails. Record via gas snapshot.
        (ok); // silence warning
    }}""")

        # stress (3x loop) using positive args
        pos_arglist = ", ".join(pos_args) if pos_args else ""
        stress_tests.append(f"""
    function test_stress_{fn}() public {{
        {contract_name} s = new {contract_name}();
        for (uint i=0; i<3; i++) {{
            s.{fn}({pos_arglist});
        }}
    }}""")

    neg_block = "\n".join(neg_tests)
    stress_block = "\n".join(stress_tests)

    # build EoP tests for sensitive functions
    eop_tests = []
    contract_meta = next((c for c in flows.get('contracts', []) if c['name'] == contract_name), None) or {}
    for fn in uniq_fns:
        if not _is_sensitive_fn(fn):
            continue
        types = []
        pos_args = []
        for cfn in contract_meta.get('functions', []):
            if cfn['name'] == fn:
                types = [i.get('type','') for i in cfn.get('inputs', [])]
                pos_args = [ _default_arg(i.get('type','')) for i in cfn.get('inputs', []) ]
                break
        sig = f"{fn}({','.join(types)})"
        arglist = (', ' + ', '.join(pos_args)) if pos_args else ''
        eop_tests.append(f"""
    function test_eop_block_{fn}() public {{
        {contract_name} s = new {contract_name}();
        Attacker a = new Attacker(address(s));
        bool ok = a.attack(abi.encodeWithSignature("{sig}"{arglist}));
        assert(!ok);
    }}""")
    eop_block = "\n".join(eop_tests)

    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "{contract_file_rel}";
{ATTACKER_SNIPPET}

contract GENERATED_{contract_name}_{uniq_fns[0]} {{

    function test_journey() public {{
        {contract_name} s = new {contract_name}();
{happy_body}
    }}
{neg_block}
{stress_block}
{eop_block}
}}
"""

def generate_foundry_tests(flows: Dict[str,Any], journeys: Dict[str,Any], work_src: Path, outdir: Path) -> Dict[str,Any]:
    tests_idx = {"tests": []}
    root_tests = outdir / "tests" / "evm"
    for j in journeys.get("journeys", []):
        jid = j["id"]
        steps = j.get("steps", [])
        if not steps:
            continue
        c_name = steps[0]["contract"]
        proj = root_tests / jid
        src = proj / "src"
        test = proj / "test"
        src.mkdir(parents=True, exist_ok=True)
        test.mkdir(parents=True, exist_ok=True)
        # copy all sources from work/src into project src
        if work_src.exists():
            shutil.copytree(work_src, src, dirs_exist_ok=True)
        # find defining file for import path
        cfile = _find_contract_file(src, c_name)
        if not cfile:
            (proj / "SKIPPED.txt").write_text(f"Contract file for {c_name} not found.")
            continue
        rel = Path("..") / "src" / cfile.relative_to(src)
        code = _make_test_code(str(rel).replace("\\", "/"), c_name, steps, flows)
        tname = _test_contract_name(jid)
        tfile = test / f"{tname}.t.sol"
        tfile.write_text(code)
        # minimal foundry.toml
        (proj / "foundry.toml").write_text("[profile.default]\nsrc = 'src'\ntest = 'test'\n")
        tests_idx["tests"].append({
            "id": f"{jid}_generated",
            "journey_id": jid,
            "kind": "generated",
            "tool": "foundry",
            "files": [str(tfile)]
        })
    (outdir / "tests.json").write_text(json.dumps(tests_idx, indent=2))
    return tests_idx
