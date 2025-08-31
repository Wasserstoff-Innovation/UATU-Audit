"""
Run indexer for scanning audit outputs and building dashboard data.
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

class RunIndexer:
    """Indexes audit runs for dashboard display."""
    
    def __init__(self, cache_ttl: int = 10):
        self.cache_ttl = cache_ttl
        self.last_scan = 0
        self.cached_runs: List[Dict[str, Any]] = []
        self.cached_portfolio: Optional[Dict[str, Any]] = None
    
    def scan_runs(self, base_path: str = ".") -> List[Dict[str, Any]]:
        """Scan for audit runs and return indexed data."""
        current_time = time.time()
        
        # Return cached data if still valid
        if current_time - self.last_scan < self.cache_ttl:
            return self.cached_runs
        
        runs = []
        base_path_obj = Path(base_path)
        
        # Get audit roots from environment
        audits_root = os.getenv('AUDITS_ROOT', 'audits')
        extra_roots = os.getenv('EXTRA_ROOTS', 'out').split(':')
        
        # Scan all roots
        all_roots = [audits_root] + extra_roots
        
        for root_name in all_roots:
            root_dir = base_path_obj / root_name
            if not root_dir.exists():
                continue
                
            print(f"🔍 Scanning audit root: {root_name}")
            
            # Scan individual audit runs in this root
            for run_dir in sorted(root_dir.iterdir(), reverse=True):
                if not run_dir.is_dir():
                    continue
                
                run_data = self._index_run(run_dir, root_name)
                if run_data:
                    runs.append(run_data)
        
        # Sort all runs by timestamp (newest first)
        runs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Cache the results
        self.cached_runs = runs
        self.last_scan = current_time
        
        return runs
    
    def scan_portfolio(self, base_path: str = ".") -> Optional[Dict[str, Any]]:
        """Scan for latest portfolio data."""
        current_time = time.time()
        
        # Return cached data if still valid
        if current_time - self.last_scan < self.cache_ttl:
            return self.cached_portfolio
        
        portfolio_dir = Path(base_path) / "out-portfolio"
        
        if not portfolio_dir.exists():
            return None
        
        # Find latest portfolio run
        portfolio_runs = []
        for run_dir in portfolio_dir.iterdir():
            if run_dir.is_dir():
                portfolio_file = run_dir / "portfolio.json"
                if portfolio_file.exists():
                    portfolio_runs.append((run_dir, portfolio_file.stat().st_mtime))
        
        if not portfolio_runs:
            return None
        
        # Get the most recent
        latest_dir, _ = max(portfolio_runs, key=lambda x: x[1])
        portfolio_data = self._index_portfolio(latest_dir)
        
        # Cache the result
        self.cached_portfolio = portfolio_data
        self.last_scan = current_time
        
        return portfolio_data
    
    def _index_run(self, run_dir: Path, root_name: str) -> Optional[Dict[str, Any]]:
        """Index a single audit run."""
        try:
            # Extract timestamp from directory name
            ts = run_dir.name
            
            # Check for required files
            risk_file = run_dir / "runs" / "risk" / "risk.json"
            report_html = run_dir / "report.html"
            report_pdf = run_dir / "report.pdf"
            
            if not risk_file.exists() or not report_html.exists():
                return None
            
            # Parse risk data
            with open(risk_file) as f:
                risk_data = json.load(f)
            
            summary = risk_data.get('summary', {})
            
            # Determine contract ID and kind
            contract_id = "unknown"
            kind = "unknown"
            
            # Try to extract from risk data
            by_function = risk_data.get('by_function', {})
            if by_function:
                # Extract contract name from first function key
                first_key = list(by_function.keys())[0]
                if '.' in first_key:
                    contract_id = first_key.split('.')[0]
            
            # Try to determine kind from contract ID
            if contract_id.startswith('evm-'):
                kind = 'evm'
            elif contract_id.startswith('stellar-'):
                kind = 'stellar'
            
            return {
                'ts': ts,
                'path': str(run_dir),
                'grade': summary.get('grade', 'Unknown'),
                'overall': summary.get('overall', 0.0),
                'delta': summary.get('delta_overall', 0.0),
                'kind': kind,
                'id': contract_id,
                'has_pdf': report_pdf.exists(),
                'has_html': report_html.exists(),
                'risk_file': str(risk_file),
                'report_html': str(report_html),
                'report_pdf': str(report_pdf) if report_pdf.exists() else None,
                'timestamp': datetime.now().isoformat() # Add timestamp for sorting
            }
            
        except Exception as e:
            print(f"Error indexing run {run_dir}: {e}")
            return None
    
    def _index_portfolio(self, portfolio_dir: Path) -> Optional[Dict[str, Any]]:
        """Index portfolio data."""
        try:
            portfolio_file = portfolio_dir / "portfolio.json"
            if not portfolio_file.exists():
                return None
            
            with open(portfolio_file) as f:
                portfolio_data = json.load(f)
            
            summary = portfolio_data.get('summary', {})
            
            return {
                'ts': portfolio_dir.name,
                'path': str(portfolio_dir),
                'grade': summary.get('grade', 'Unknown'),
                'overall': summary.get('overall', 0.0),
                'delta': summary.get('delta_overall', 0.0),
                'contract_count': len(portfolio_data.get('by_contract', {})),
                'portfolio_file': str(portfolio_file),
                'portfolio_html': str(portfolio_dir / "portfolio.report.html"),
                'portfolio_pdf': str(portfolio_dir / "portfolio.report.pdf"),
                'portfolio_csv': str(portfolio_dir / "portfolio.heatmap.csv"),
                'badge': str(portfolio_dir / "badge-portfolio.svg"),
                'sparkline': str(portfolio_dir / "sparkline-portfolio.svg")
            }
            
        except Exception as e:
            print(f"Error indexing portfolio {portfolio_dir}: {e}")
            return None
    
    def get_run_by_ts(self, ts: str, base_path: str = ".") -> Optional[Dict[str, Any]]:
        """Get specific run by timestamp."""
        runs = self.scan_runs(base_path)
        for run in runs:
            if run['ts'] == ts:
                return run
        return None
    
    def get_portfolio_by_ts(self, ts: str, base_path: str = ".") -> Optional[Dict[str, Any]]:
        """Get specific portfolio by timestamp."""
        portfolio_dir = Path(base_path) / "out-portfolio" / ts
        if portfolio_dir.exists():
            return self._index_portfolio(portfolio_dir)
        return None
