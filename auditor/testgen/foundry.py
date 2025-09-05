from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
from ..llm.engine import LLMMeta, generate_assertion_fn
from ..runners.forge_runner import forge_build
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

def _eop_gate(contract_name: str, fn_name: str, threats: dict | None, eop_mode: str) -> tuple[bool,str]:
    fl = (fn_name or '')
    has_heur = _is_sensitive_fn(fl)
    has_stride = False
    if threats:
        key = f"{contract_name}.{fn_name}"
        bucket = threats.get('by_function', {}).get(key, {}) if isinstance(threats, dict) else {}
        eops = (bucket or {}).get('elevation_of_privilege') or []
        has_stride = len(eops) > 0
    m = (eop_mode or 'auto').lower()
    if m == 'off':
        return False, 'off'
    if m == 'stride':
        return has_stride, 'stride'
    if m == 'heuristic':
        return has_heur, 'heuristic'
    if m == 'both':
        src = 'stride+heuristic' if (has_stride and has_heur) else ('stride' if has_stride else ('heuristic' if has_heur else 'none'))
        return has_stride or has_heur, src
    # auto: prefer stride if present, else fallback to heuristic
    if has_stride:
        return True, 'stride'
    return (has_heur, 'heuristic' if has_heur else 'none')

def _append_llm_and_precheck(project_dir: Path, test_file: Path, marker_name: str, snippet: str) -> tuple[bool, str]:
    """Append LLM snippet wrapped in markers, forge build, and revert on failure.
    Returns (kept, reason)."""
    start_m = f"// >>> LLM:{marker_name} BEGIN"
    end_m = f"// <<< LLM:{marker_name} END"
    original = test_file.read_text()
    patched = original + f"\n\n{start_m}\n{snippet}\n{end_m}\n"
    test_file.write_text(patched)

    code, out, err = forge_build(project_dir)
    if code == 0:
        return True, "ok"
    # revert
    test_file.write_text(original)
    return False, "compile_error"

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

def _make_test_code(contract_file_rel: str, contract_name: str, steps: List[Dict[str, Any]], flows: Dict[str,Any], threats: dict | None, eop_mode: str, llm_meta: LLMMeta | None, journey_id: str, abi_map: dict | None, is_standard_contract: bool = False) -> str:
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
        ok, _src = _eop_gate(contract_name, fn, threats, eop_mode)
        if not ok:
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

    # LLM functions are now appended post-write with compile precheck

    # For standard OpenZeppelin contracts, import from @openzeppelin directly
    # For custom contracts, use relative path to src_repo
    import_stmt = f'import "{contract_file_rel}";' if not is_standard_contract else f'import "{contract_file_rel}";'
    
    return f"""// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
{import_stmt}
{ATTACKER_SNIPPET}

contract GENERATED_{contract_name}_{uniq_fns[0]} {{

    function test_journey() public {{
        {contract_name} s = new {contract_name}();
{happy_body}
    }}
{neg_block}
{stress_block}
{eop_block}
// LLM functions appended post-write with compile precheck
}}
"""

def generate_foundry_tests(flows: Dict[str,Any], journeys: Dict[str,Any], work_src: Path, outdir: Path,
    threats: dict | None = None, eop_mode: str = 'auto', llm_meta: LLMMeta | None = None, abi_map: dict | None = None, llm_policy=None) -> Dict[str,Any]:
    tests_idx = {"tests": []}
    root_tests = outdir / "tests" / "evm"
    
    # Create shared source directory ONCE instead of copying for each test
    shared_src = root_tests / "shared_source"
    if work_src.exists() and not shared_src.exists():
        shared_src.mkdir(parents=True, exist_ok=True)
        def _ignore(dir, names):
            ignore = {'.git', '.hg', '.svn', '.idea', '.vscode', 'node_modules', 'target', 'build', 'dist'}
            return [n for n in names if n in ignore]
        shutil.copytree(work_src, shared_src, dirs_exist_ok=True, ignore=_ignore)
        print(f"Created shared source directory at: {shared_src}")
    
    for j in journeys.get("journeys", []):
        jid = j["id"]
        steps = j.get("steps", [])
        if not steps:
            continue
        c_name = steps[0]["contract"]
        
        # Create lightweight test project - only test directory, no source copy
        proj = root_tests / jid
        test = proj / "test"
        test.mkdir(parents=True, exist_ok=True)
        
        # No src directory needed - using remappings to shared source
        # No src_repo copy - using shared_source instead
        # Use OpenZeppelin remapping for standard contracts, otherwise look in shared source
        is_standard = c_name in ["Ownable", "AccessControl", "ERC20", "ERC721", "ERC1155"]
        if is_standard:
            if c_name in ["Ownable", "AccessControl"]:
                import_path = f"@openzeppelin/contracts/access/{c_name}.sol"
            else:
                # ERC20, ERC721, ERC1155
                import_path = f"@openzeppelin/contracts/token/ERC{c_name[3:]}/{c_name}.sol"
        else:
            # find defining file for custom contracts in shared source
            cfile = _find_contract_file(shared_src, c_name)
            if not cfile:
                (proj / "SKIPPED.txt").write_text(f"Contract file for {c_name} not found in shared source.")
                continue
            # Use remapping to shared source instead of relative path
            rel_path = cfile.relative_to(shared_src)
            import_path = f"@shared/{rel_path}".replace("\\", "/")
        code = _make_test_code(import_path, c_name, steps, flows, threats, eop_mode, llm_meta, jid, abi_map, is_standard)
        tname = _test_contract_name(jid)
        tfile = test / f"{tname}.t.sol"
        tfile.write_text(code)
        
        # --- LLM POST-WRITE: append snippets one-by-one with compile precheck ---
        if llm_meta is not None and llm_meta.enabled:
            # Collect uniq functions of this journey again (same logic as in _make_test_code)
            uniq_fns = []
            for st in steps:
                fn = st.get("function")
                if fn and fn not in uniq_fns:
                    uniq_fns.append(fn)

            # find meta of contract & param types
            contract_meta = None
            for c in flows.get("contracts", []):
                if c.get("name") == c_name:
                    contract_meta = c
                    break

            tmap = (threats or {}).get('by_function', {}) if isinstance(threats, dict) else {}

            for fn in uniq_fns:
                # resolve param types + default args
                types = []
                pos_args = []
                for cfn in (contract_meta or {}).get('functions', []):
                    if cfn.get('name') == fn:
                        types = [i.get('type','') for i in cfn.get('inputs', [])]
                        pos_args = [ _default_arg(i.get('type','')) for i in cfn.get('inputs', []) ]
                        break
                key = f"{c_name}.{fn}"
                bucket = tmap.get(key, {}) if isinstance(tmap, dict) else {}

                # Use LLM policy for cost-aware assertion generation
                from ..llm.policy import LLMBudget
                from ..llm.engine import generate_assertion_fn
                
                # Check if we can make a call within budget
                # This would need access to the policy instance, so we'll use the original for now
                # TODO: Pass policy instance through the call chain
                res = generate_assertion_fn(outdir, jid, c_name, fn, types, pos_args, bucket, llm_meta, abi_map=abi_map, llm_policy=llm_policy)
                # Cache already written by engine; only include if valid AND compiles
                if res.get("added") and res.get("snippet"):
                    kept, reason = _append_llm_and_precheck(project_dir=proj, test_file=tfile, marker_name=f"{jid}__{fn}", snippet=res["snippet"])
                    # Always update the meta.json with the reason (ok or compile_error)
                    try:
                        meta_path = (outdir / "runs" / "llm" / f"{jid}__{fn}.meta.json")
                        if meta_path.exists():
                            j = json.loads(meta_path.read_text())
                        else:
                            j = {}
                        j["reason"] = reason
                        meta_path.write_text(json.dumps(j, indent=2))
                    except Exception:
                        pass
        
        # foundry.toml with comprehensive remappings for OpenZeppelin and shared source
        # Calculate relative path from this project to shared source
        shared_rel = Path("..") / "shared_source"
        foundry_config = f"""[profile.default]
test = 'test'
libs = ['lib']
remappings = [
    '@openzeppelin/=lib/openzeppelin-contracts/',
    '@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/',
    '@openzeppelin/contracts-upgradeable/=lib/openzeppelin-contracts-upgradeable/contracts/',
    '@shared/={shared_rel}/'
]
"""
        (proj / "foundry.toml").write_text(foundry_config)
        tests_idx["tests"].append({
            "id": f"{jid}_generated",
            "journey_id": jid,
            "kind": "generated",
            "tool": "foundry",
            "files": [str(tfile)]
        })
    (outdir / "tests.json").write_text(json.dumps(tests_idx, indent=2))
    return tests_idx
