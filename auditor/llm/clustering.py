"""
MINI clustering prompts and caches for function grouping.

Implements the function clustering functionality as specified in the requirements.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class FunctionInfo:
    """Information about a function for clustering."""
    name: str
    visibility: str
    mutability: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    modifiers: List[str]
    events: List[str]

@dataclass
class ClusterFeature:
    """A feature cluster of functions."""
    name: str
    fns: List[str]
    preconds: List[str]
    fixture: List[str]
    effects: List[str]

@dataclass
class ContractClusters:
    """Clustering results for a contract."""
    contract: str
    features: List[ClusterFeature]

def make_clustering_prompt(contract_name: str, functions: List[FunctionInfo], 
                          modifiers: List[str], events: List[str]) -> str:
    """Create the MINI clustering prompt as specified in requirements."""
    
    # Build function signatures
    signatures = []
    for fn in functions:
        inputs = ", ".join([f"{inp.get('type', '')} {inp.get('name', '')}" for inp in fn.inputs])
        outputs = f" returns ({', '.join([out.get('type', '') for out in fn.outputs])})" if fn.outputs else ""
        sig = f"{fn.name}({inputs}){outputs}"
        signatures.append(sig)
    
    # Build modifiers list
    modifiers_str = ", ".join(modifiers) if modifiers else "none"
    
    # Build events list
    events_str = ", ".join(events) if events else "none"
    
    prompt = f"""Task: Group these function signatures into 3–6 features. For each feature, list implied preconditions, minimal fixture setup, and important side effects (events/vars). Avoid speculation; use names/modifiers.

Input: contract {contract_name} {{ signatures[], modifiers[], events[] }}

Signatures: {signatures}
Modifiers: {modifiers_str}
Events: {events_str}

Output JSON: {{"features":[{{"name":"...","fns":[...],"preconds":[...],"fixture":[...],"effects":[...]}}]}}"""
    
    return prompt

def parse_clustering_response(response: str) -> Optional[ContractClusters]:
    """Parse the LLM response into ContractClusters."""
    try:
        # Try to extract JSON from response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start == -1 or end == 0:
            return None
        
        json_str = response[start:end]
        data = json.loads(json_str)
        
        features = []
        for feature_data in data.get("features", []):
            feature = ClusterFeature(
                name=feature_data.get("name", ""),
                fns=feature_data.get("fns", []),
                preconds=feature_data.get("preconds", []),
                fixture=feature_data.get("fixture", []),
                effects=feature_data.get("effects", [])
            )
            features.append(feature)
        
        return ContractClusters(
            contract=data.get("contract", ""),
            features=features
        )
        
    except Exception:
        return None

def cluster_contract_functions(contract_name: str, functions: List[FunctionInfo], 
                              modifiers: List[str], events: List[str],
                              llm_policy, provider_meta, repo_commit_sha: str = "unknown") -> Optional[ContractClusters]:
    """Cluster functions for a contract using MINI LLM calls."""
    
    if not llm_policy or not provider_meta.enabled:
        return None
    
    from .policy import LLMBudget
    
    # Create prompt
    prompt = make_clustering_prompt(contract_name, functions, modifiers, events)
    
    # Make LLM call with MINI budget
    result = llm_policy.make_call(
        budget=LLMBudget.MINI,
        prompt_template_id="function_clustering",
        repo_commit_sha=repo_commit_sha,
        contract_name=contract_name,
        scope="clustering",
        prompt=prompt,
        provider_meta=provider_meta
    )
    
    if not result.get("success"):
        return None
    
    # Parse response
    response = result.get("output", "")
    clusters = parse_clustering_response(response)
    
    if clusters:
        clusters.contract = contract_name
    
    return clusters

def save_clusters(outdir: Path, clusters: ContractClusters):
    """Save clustering results to clusters.json."""
    clusters_file = outdir / "clusters.json"
    
    data = {
        "contract": clusters.contract,
        "features": [
            {
                "name": feature.name,
                "fns": feature.fns,
                "preconds": feature.preconds,
                "fixture": feature.fixture,
                "effects": feature.effects
            }
            for feature in clusters.features
        ]
    }
    
    clusters_file.write_text(json.dumps(data, indent=2))

def load_clusters(outdir: Path) -> Optional[ContractClusters]:
    """Load clustering results from clusters.json."""
    clusters_file = outdir / "clusters.json"
    
    if not clusters_file.exists():
        return None
    
    try:
        data = json.loads(clusters_file.read_text())
        
        features = []
        for feature_data in data.get("features", []):
            feature = ClusterFeature(
                name=feature_data.get("name", ""),
                fns=feature_data.get("fns", []),
                preconds=feature_data.get("preconds", []),
                fixture=feature_data.get("fixture", []),
                effects=feature_data.get("effects", [])
            )
            features.append(feature)
        
        return ContractClusters(
            contract=data.get("contract", ""),
            features=features
        )
        
    except Exception:
        return None

def extract_functions_from_flows(flows: Dict[str, Any], contract_name: str) -> List[FunctionInfo]:
    """Extract function information from flows data."""
    functions = []
    
    for contract in flows.get("contracts", []):
        if contract.get("name") == contract_name:
            for fn_data in contract.get("functions", []):
                fn = FunctionInfo(
                    name=fn_data.get("name", ""),
                    visibility=fn_data.get("visibility", ""),
                    mutability=fn_data.get("mutability", ""),
                    inputs=fn_data.get("inputs", []),
                    outputs=fn_data.get("outputs", []),
                    modifiers=fn_data.get("modifiers", []),
                    events=fn_data.get("events", [])
                )
                functions.append(fn)
            break
    
    return functions

def extract_modifiers_from_flows(flows: Dict[str, Any], contract_name: str) -> List[str]:
    """Extract modifiers from flows data."""
    for contract in flows.get("contracts", []):
        if contract.get("name") == contract_name:
            return contract.get("modifiers", [])
    return []

def extract_events_from_flows(flows: Dict[str, Any], contract_name: str) -> List[str]:
    """Extract events from flows data."""
    for contract in flows.get("contracts", []):
        if contract.get("name") == contract_name:
            return [event.get("name", "") for event in contract.get("events", [])]
    return []
