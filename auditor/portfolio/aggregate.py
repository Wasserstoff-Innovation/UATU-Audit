from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import csv

def validate_portfolio(portfolio: Dict[str, Any]) -> bool:
    """Validate portfolio data against schema requirements."""
    required_keys = ["version", "generated_at", "summary", "by_contract"]
    for key in required_keys:
        if key not in portfolio:
            raise ValueError(f"Missing required key: {key}")
    
    summary = portfolio["summary"]
    summary_keys = ["overall", "grade", "delta_overall", "buckets", "top_contracts"]
    for key in summary_keys:
        if key not in summary:
            raise ValueError(f"Missing required summary key: {key}")
    
    # Validate types
    if not isinstance(summary["overall"], (int, float)):
        raise ValueError("summary.overall must be a number")
    
    if not isinstance(summary["grade"], str):
        raise ValueError("summary.grade must be a string")
    
    if not isinstance(summary["delta_overall"], (int, float)):
        raise ValueError("summary.delta_overall must be a number")
    
    if not isinstance(summary["buckets"], dict):
        raise ValueError("summary.buckets must be a dictionary")
    
    if not isinstance(summary["top_contracts"], list):
        raise ValueError("summary.top_contracts must be a list")
    
    return True

def _grade(score: float) -> str:
    """Grade assignment logic (same as risk scoring)."""
    if score >= 80:
        return "Critical"
    elif score >= 60:
        return "High"
    elif score >= 40:
        return "Medium"
    elif score >= 20:
        return "Low"
    else:
        return "Info"

def _extract_contract_id(risk_file_path: Path) -> str:
    """Extract contract ID from risk.json path."""
    # Try to find matrix.id in the risk.json content first
    try:
        risk_data = json.loads(risk_file_path.read_text())
        # Look for matrix.id in metadata if present
        if "matrix_id" in risk_data:
            return risk_data["matrix_id"]
    except:
        pass
    
    # Fallback: use parent directory name
    parent_dir = risk_file_path.parent.parent.parent.parent.name
    if parent_dir and parent_dir != "runs":
        return parent_dir
    
    # Final fallback: use filename stem
    return risk_file_path.stem

def _compute_buckets(risk_data: Dict[str, Any]) -> Dict[str, int]:
    """Compute grade buckets from risk data."""
    buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    
    # Try to get buckets from summary first
    summary_buckets = risk_data.get("summary", {}).get("buckets")
    if summary_buckets:
        for grade, count in summary_buckets.items():
            if grade in buckets:
                buckets[grade] = count
        return buckets
    
    # Fallback: compute from by_function if available
    by_function = risk_data.get("by_function", {})
    if by_function:
        for func_data in by_function.values():
            grade = func_data.get("grade", "Info")
            if grade in buckets:
                buckets[grade] += 1
    
    return buckets

def aggregate_portfolio(
    risk_files: List[Path],
    baseline_path: Optional[Path] = None,
    outdir: Path = Path("out-portfolio")
) -> Dict[str, Any]:
    """Aggregate risk data from multiple contracts into portfolio view."""
    
    # Load baseline if provided
    baseline = None
    if baseline_path and baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text())
        except Exception:
            pass
    
    # Process each contract
    contracts = {}
    all_scores = []
    
    for risk_file in risk_files:
        try:
            risk_data = json.loads(risk_file.read_text())
            contract_id = _extract_contract_id(risk_file)
            
            # Extract contract data
            summary = risk_data.get("summary", {})
            overall = float(summary.get("overall", 0.0))
            grade = summary.get("grade", _grade(overall))
            buckets = _compute_buckets(risk_data)
            
            # Compute delta vs baseline
            delta = 0.0
            if baseline and "by_contract" in baseline:
                prev_score = baseline["by_contract"].get(contract_id, {}).get("overall", 0.0)
                delta = overall - float(prev_score)
            
            contracts[contract_id] = {
                "overall": overall,
                "grade": grade,
                "delta": round(delta, 1),
                "buckets": buckets
            }
            
            all_scores.append(overall)
            
        except Exception as e:
            print(f"[warn] Failed to process {risk_file}: {e}")
            continue
    
    if not contracts:
        raise ValueError("No valid risk files found")
    
    # Compute portfolio summary
    portfolio_overall = sum(all_scores) / len(all_scores)  # Average
    portfolio_grade = _grade(portfolio_overall)
    
    # Aggregate buckets across all contracts
    portfolio_buckets = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    for contract_data in contracts.values():
        for grade, count in contract_data["buckets"].items():
            if grade in portfolio_buckets:
                portfolio_buckets[grade] += count
    
    # Compute portfolio delta
    portfolio_delta = 0.0
    if baseline and "summary" in baseline:
        prev_portfolio = baseline["summary"].get("overall", 0.0)
        portfolio_delta = portfolio_overall - float(prev_portfolio)
    
    # Top contracts by score
    top_contracts = sorted(
        [{"id": k, "overall": v["overall"], "grade": v["grade"], "delta": v["delta"]} 
         for k, v in contracts.items()],
        key=lambda x: x["overall"], reverse=True
    )[:10]  # Top 10
    
    # Build portfolio data
    portfolio = {
        "version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "overall": round(portfolio_overall, 1),
            "grade": portfolio_grade,
            "delta_overall": round(portfolio_delta, 1),
            "buckets": portfolio_buckets,
            "top_contracts": top_contracts
        },
        "by_contract": contracts
    }
    
    return portfolio

def export_portfolio_csv(portfolio: Dict[str, Any], outdir: Path) -> Path:
    """Export portfolio data to CSV heatmap."""
    csv_path = outdir / "portfolio.heatmap.csv"
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "contract_id", "kind", "overall", "grade", "delta", "ts",
            "bucket_critical", "bucket_high", "bucket_medium", "bucket_low", "bucket_info"
        ])
        
        for contract_id, data in portfolio["by_contract"].items():
            buckets = data["buckets"]
            # Extract kind from contract_id (evm-* or stellar-*)
            kind = "evm" if contract_id.startswith("evm-") else "stellar" if contract_id.startswith("stellar-") else "unknown"
            # Extract timestamp from portfolio generation
            ts = portfolio.get("generated_at", "")
            writer.writerow([
                contract_id,
                kind,
                data["overall"],
                data["grade"],
                data["delta"],
                ts,
                buckets.get("Critical", 0),
                buckets.get("Medium", 0),
                buckets.get("High", 0),
                buckets.get("Low", 0),
                buckets.get("Info", 0)
            ])
    
    return csv_path

def save_portfolio(portfolio: Dict[str, Any], outdir: Path) -> Path:
    """Save portfolio data to JSON file."""
    outdir.mkdir(parents=True, exist_ok=True)
    portfolio_path = outdir / "portfolio.json"
    
    # Validate against schema before saving
    try:
        validate_portfolio(portfolio)
        validation_status = "valid"
    except Exception as e:
        validation_status = "invalid"
        # Save error details
        error_path = outdir / "portfolio.error.json"
        error_data = {
            "error": str(e),
            "validation_failed_at": datetime.utcnow().isoformat() + "Z",
            "portfolio_data": portfolio
        }
        with open(error_path, "w") as f:
            json.dump(error_data, f, indent=2)
    
    # Save portfolio data
    with open(portfolio_path, "w") as f:
        json.dump(portfolio, f, indent=2)
    
    # Add validation status to portfolio
    portfolio["_validation"] = validation_status
    
    return portfolio_path
