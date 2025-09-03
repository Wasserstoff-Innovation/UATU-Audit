from __future__ import annotations
import os, json
from pathlib import Path
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed

class LLMMeta:
    def __init__(self, enabled: bool, provider: str = "none", model: str = "", reason: str = ""):
        self.enabled = enabled
        self.provider = provider
        self.model = model
        self.reason = reason

def detect_provider(explicit: Optional[str] = None) -> LLMMeta:
    mode = (explicit or "auto").lower()
    if mode == "off":
        return LLMMeta(False, "none", "", "flag_off")
    # autodetect by env
    if mode in ("auto","openai"):
        if os.getenv("OPENAI_API_KEY"):
            return LLMMeta(True, "openai", os.getenv("OPENAI_MODEL","gpt-4o-mini"), "")
        if mode == "openai":
            return LLMMeta(False, "openai", "", "no_api_key")
    if mode in ("auto","anthropic"):
        if os.getenv("ANTHROPIC_API_KEY"):
            return LLMMeta(True, "anthropic", os.getenv("ANTHROPIC_MODEL","claude-3-5-sonnet-20240620"), "")
        if mode == "anthropic":
            return LLMMeta(False, "anthropic", "", "no_api_key")
    return LLMMeta(False, "none", "", "no_provider")

PROMPT_HEADER = """You generate Solidity Foundry tests (pragma ^0.8.20) that assert behavior of a specific function call.
Constraints:
- Output ONLY a single Solidity test function inside a contract (no imports, no pragma, no comments outside the function).
- Use built-in `assert` or `require` or `vm.expectRevert` if needed (forge-std may be available).
- You may assume the contract under test is already deployed to variable `s` of type {contract}.
- Name the function exactly: test_llm_{fn}.
- The function should execute the call `{call_sig}` and assert postconditions true.
- Prefer simple, deterministic checks: state diffs, event counts (if available), revert on invalid input, invariants (e.g., non-decreasing), bounds, ownership checks.
- Do NOT write external helper contracts or imports.
"""

def _cache_paths(outdir: Path, journey_id: str, fn: str):
    base = outdir / "runs" / "llm"
    base.mkdir(parents=True, exist_ok=True)
    stem = f"{journey_id}__{fn}"
    return base / f"{stem}.prompt.txt", base / f"{stem}.response.txt", base / f"{stem}.meta.json"

def _write_cache(pp: Path, rp: Path, mp: Path, prompt: str, response: str, meta: Dict[str,Any]):
    pp.write_text(prompt)
    rp.write_text(response)
    mp.write_text(json.dumps(meta, indent=2))

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
def _call_openai(model: str, prompt: str) -> str:
    import openai
    client = openai.OpenAI()
    r = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":"You are a senior smart contract auditor."},
                  {"role":"user","content":prompt}],
        temperature=0
    )
    return r.choices[0].message.content.strip()

@retry(stop=stop_after_attempt(2), wait=wait_fixed(1))
def _call_anthropic(model: str, prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=model,
        max_tokens=1200,
        messages=[{"role":"user","content":prompt}]
    )
    # anthropic returns a list of content blocks
    return "".join(getattr(b,"text",str(b)) for b in r.content).strip()

def make_prompt(contract_name: str, fn_name: str, types: list[str], args_preview: list[str], threats_for_fn: dict, abi_map: dict | None) -> str:
    call_sig = f"{fn_name}({', '.join(args_preview)})"
    # ABI slice
    abi_f = (abi_map or {}).get('functions', {}).get(f"{contract_name}.{fn_name}", [])
    events = (abi_map or {}).get('events', {}).get(contract_name, {})
    errors = (abi_map or {}).get('errors', {})  # empty for now unless flows support
    
    threat_lines = []
    for k,v in (threats_for_fn or {}).items():
        if v: threat_lines.append(f"- {k}: {', '.join(v[:4])}")
    threats_txt = "\n".join(threat_lines) if threat_lines else "none"
    body = f"""
Contract: {contract_name}
Function: {fn_name}({', '.join(types)})
Likely call in test: s.{call_sig};

ABI inputs: {abi_f}
Known events for this contract: {list(events.keys())}
Custom errors (if any): {list(errors.keys())}
STRIDE threats (if any):
{threats_txt}

Constraints for using events & reverts:
- Prefer state assertions; if you assert reverts, use generic `vm.expectRevert()` (no selector) to stay robust.
- If you assert events, you MAY use `vm.recordLogs()` and `vm.getRecordedLogs()` (assuming forge-std `Test` base exists), or simply assert state diffs if unsure.
- Do not import new files; the test must compile inside existing harness.
"""
    return PROMPT_HEADER.format(contract=contract_name, fn=fn_name, call_sig=f"s.{call_sig}") + "\n" + body

def generate_assertion_fn(outdir: Path, journey_id: str, contract_name: str, fn_name: str,
                          input_types: list[str], default_args: list[str], threats_for_fn: dict,
                          provider_meta: LLMMeta, abi_map: dict | None = None, llm_policy=None) -> dict:
    # guard
    if not provider_meta.enabled:
        return {"added": False, "reason": provider_meta.reason or "disabled", "provider": provider_meta.provider, "model": provider_meta.model}
    
    # Use LLM policy if available
    if llm_policy:
        from .policy import LLMBudget
        prompt = make_prompt(contract_name, fn_name, input_types, default_args, threats_for_fn, abi_map)
        
        result = llm_policy.make_call(
            budget=LLMBudget.MINI,
            prompt_template_id="assertion_augment",
            repo_commit_sha="unknown",  # Could be extracted from git
            contract_name=contract_name,
            scope=f"{journey_id}_{fn_name}",
            prompt=prompt,
            provider_meta=provider_meta
        )
        
        if result.get("success"):
            response = result.get("output", "")
            # minimal sanity: must contain `function test_llm_...(` and a closing brace.
            ok = ("function test_llm_" in response) and ("{" in response) and ("}" in response)
            return {
                "added": ok, 
                "reason": "ok" if ok else "invalid_snippet", 
                "provider": provider_meta.provider, 
                "model": provider_meta.model, 
                "snippet": response,
                "cached": result.get("cached", False),
                "tokens": result.get("tokens", 0)
            }
        else:
            return {
                "added": False, 
                "reason": result.get("reason", "failed"), 
                "provider": provider_meta.provider, 
                "model": provider_meta.model,
                "error": result.get("error")
            }
    
    # Fallback to original implementation
    prompt = make_prompt(contract_name, fn_name, input_types, default_args, threats_for_fn, abi_map)
    pp, rp, mp = _cache_paths(outdir, journey_id, fn_name)
    try:
        if provider_meta.provider == "openai":
            response = _call_openai(provider_meta.model, prompt)
        elif provider_meta.provider == "anthropic":
            response = _call_anthropic(provider_meta.model, prompt)
        else:
            return {"added": False, "reason": "no_provider", "provider": provider_meta.provider, "model": provider_meta.model}
        _write_cache(pp, rp, mp, prompt, response, {"provider": provider_meta.provider, "model": provider_meta.model})
        # minimal sanity: must contain `function test_llm_...(` and a closing brace.
        ok = ("function test_llm_" in response) and ("{" in response) and ("}" in response)
        return {"added": ok, "reason": "ok" if ok else "invalid_snippet", "provider": provider_meta.provider, "model": provider_meta.model, "snippet": response}
    except Exception as e:
        _write_cache(pp, rp, mp, prompt, f"ERROR: {e}", {"error": str(e), "provider": provider_meta.provider, "model": provider_meta.model})
        return {"added": False, "reason": "error", "error": str(e), "provider": provider_meta.provider, "model": provider_meta.model}
