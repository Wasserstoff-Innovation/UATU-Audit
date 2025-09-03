"""
Cost-aware LLM policy and caching for UatuAudit.

Implements budget caps, caching, and prompt templates as specified in the requirements.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

class LLMBudget(Enum):
    NANO = "nano"      # 1-2 calls (repo inventory, directory summaries)
    MINI = "mini"      # per-contract clustering, journey planning, assertions
    LARGE = "large"    # rare/expensive, only after compile-precheck fails 2x

@dataclass
class LLMConfig:
    """LLM configuration with budget caps and settings."""
    enabled: bool = True
    provider: str = "none"
    model: str = ""
    budget_caps: Dict[LLMBudget, int] = None
    cache_enabled: bool = True
    max_context_chars: int = 5000
    
    def __post_init__(self):
        if self.budget_caps is None:
            self.budget_caps = {
                LLMBudget.NANO: 2,
                LLMBudget.MINI: 10,  # per contract + 3 assertions
                LLMBudget.LARGE: 0   # off by default
            }

@dataclass
class CacheEntry:
    """Cache entry for LLM responses."""
    input_hash: str
    output: str
    tokens: int
    created_at: str
    budget_used: LLMBudget
    prompt_template_id: str

class LLMPolicy:
    """Cost-aware LLM policy with caching and budget management."""
    
    def __init__(self, outdir: Path, config: Optional[LLMConfig] = None):
        self.outdir = outdir
        self.config = config or LLMConfig()
        self.cache_dir = outdir / "runs" / "llm" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Track usage per budget tier
        self.usage = {
            LLMBudget.NANO: 0,
            LLMBudget.MINI: 0,
            LLMBudget.LARGE: 0
        }
        
        # Load existing usage from metadata
        self._load_usage()
    
    def _load_usage(self):
        """Load usage tracking from metadata file."""
        meta_file = self.cache_dir / "usage.json"
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text())
                for budget_str, count in data.get("usage", {}).items():
                    try:
                        budget = LLMBudget(budget_str)
                        self.usage[budget] = count
                    except ValueError:
                        pass
            except Exception:
                pass
    
    def _save_usage(self):
        """Save usage tracking to metadata file."""
        meta_file = self.cache_dir / "usage.json"
        data = {
            "usage": {budget.value: count for budget, count in self.usage.items()},
            "config": {
                "enabled": self.config.enabled,
                "provider": self.config.provider,
                "model": self.config.model,
                "budget_caps": {budget.value: cap for budget, cap in self.config.budget_caps.items()}
            }
        }
        meta_file.write_text(json.dumps(data, indent=2))
    
    def _generate_cache_key(self, model: str, prompt_template_id: str, 
                          repo_commit_sha: str, contract_name: str, scope: str) -> str:
        """Generate cache key as specified in requirements."""
        key_data = f"{model}|{prompt_template_id}|{repo_commit_sha}|{contract_name}|{scope}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _get_cache_entry(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cached response if available."""
        if not self.config.cache_enabled:
            return None
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        
        try:
            data = json.loads(cache_file.read_text())
            return CacheEntry(**data)
        except Exception:
            return None
    
    def _save_cache_entry(self, cache_key: str, entry: CacheEntry):
        """Save response to cache."""
        if not self.config.cache_enabled:
            return
        
        cache_file = self.cache_dir / f"{cache_key}.json"
        cache_file.write_text(json.dumps({
            "input_hash": entry.input_hash,
            "output": entry.output,
            "tokens": entry.tokens,
            "created_at": entry.created_at,
            "budget_used": entry.budget_used.value,
            "prompt_template_id": entry.prompt_template_id
        }, indent=2))
    
    def can_make_call(self, budget: LLMBudget) -> bool:
        """Check if we can make a call within budget limits."""
        if not self.config.enabled:
            return False
        
        return self.usage[budget] < self.config.budget_caps[budget]
    
    def make_call(self, budget: LLMBudget, prompt_template_id: str, 
                  repo_commit_sha: str, contract_name: str, scope: str,
                  prompt: str, provider_meta) -> Dict[str, Any]:
        """Make an LLM call with caching and budget tracking."""
        if not self.can_make_call(budget):
            return {
                "success": False,
                "reason": "budget_exceeded",
                "budget": budget.value,
                "usage": self.usage[budget],
                "limit": self.config.budget_caps[budget]
            }
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            provider_meta.model, prompt_template_id, 
            repo_commit_sha, contract_name, scope
        )
        
        # Check cache first
        cached = self._get_cache_entry(cache_key)
        if cached:
            return {
                "success": True,
                "cached": True,
                "output": cached.output,
                "tokens": cached.tokens,
                "budget": budget.value
            }
        
        # Make actual LLM call
        try:
            from .engine import _call_openai, _call_anthropic
            
            if provider_meta.provider == "openai":
                response = _call_openai(provider_meta.model, prompt)
            elif provider_meta.provider == "anthropic":
                response = _call_anthropic(provider_meta.model, prompt)
            else:
                return {
                    "success": False,
                    "reason": "no_provider",
                    "provider": provider_meta.provider
                }
            
            # Estimate tokens (rough approximation)
            tokens = len(prompt.split()) + len(response.split())
            
            # Create cache entry
            import datetime
            entry = CacheEntry(
                input_hash=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                output=response,
                tokens=tokens,
                created_at=datetime.datetime.now().isoformat(),
                budget_used=budget,
                prompt_template_id=prompt_template_id
            )
            
            # Save to cache
            self._save_cache_entry(cache_key, entry)
            
            # Update usage
            self.usage[budget] += 1
            self._save_usage()
            
            return {
                "success": True,
                "cached": False,
                "output": response,
                "tokens": tokens,
                "budget": budget.value,
                "usage": self.usage[budget]
            }
            
        except Exception as e:
            return {
                "success": False,
                "reason": "error",
                "error": str(e),
                "budget": budget.value
            }
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get current usage summary."""
        return {
            "enabled": self.config.enabled,
            "provider": self.config.provider,
            "model": self.config.model,
            "usage": {budget.value: {
                "used": self.usage[budget],
                "limit": self.config.budget_caps[budget],
                "remaining": self.config.budget_caps[budget] - self.usage[budget]
            } for budget in LLMBudget},
            "cache_enabled": self.config.cache_enabled
        }

# Prompt templates as specified in requirements
REPO_SYNOPSIS_PROMPT = """Task: Given the file tree and READMEs below, list the system's goals, key components, and any explicit invariants or roles. Return 5–10 bullets, no prose, no code.

Input:
* TREE: {tree}
* README SNIPPETS: {readme_snippets}

Output JSON: {{"goals":[...], "roles":[...], "invariants":[...], "components":[...]}}"""

FUNCTION_CLUSTERING_PROMPT = """Task: Group these function signatures into 3–6 features. For each feature, list implied preconditions, minimal fixture setup, and important side effects (events/vars). Avoid speculation; use names/modifiers.

Input: contract {contract_name} {{ signatures[], modifiers[], events[] }}

Output JSON: {{"features":[{{"name":"...","fns":[...],"preconds":[...],"fixture":[...],"effects":[...]}}]}}"""

ASSERTION_AUGMENT_PROMPT = """Task: Suggest one additional assertion after this sequence to strengthen correctness. Use Foundry cheatcodes; no imports. Must compile in Solidity 0.8.XX.

Context: journey steps, ABI events, state variables

Output: a single function body (no contract), name test_llm_extra_{slug}."""

def create_llm_policy(outdir: Path, config: Optional[LLMConfig] = None) -> LLMPolicy:
    """Create an LLM policy instance with the given configuration."""
    return LLMPolicy(outdir, config)
