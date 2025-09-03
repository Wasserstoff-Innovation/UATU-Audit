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
        """Scan for audit runs and return indexed data including in-progress audits."""
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
        
        # Also scan user workspaces for in-progress audits
        user_workspace_roots = [
            Path.home() / ".uatu_audit" / "workspaces",
            Path("/tmp") / "uatu_audit" / "workspaces",
            Path.cwd() / "tmp" / "workspaces"
        ]
        
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
        
        # Scan user workspaces for in-progress audits
        only_user = os.getenv('UATU_WORKSPACE_USER')
        for workspace_root in user_workspace_roots:
            if not workspace_root.exists():
                print(f"  Workspace root does not exist: {workspace_root}")
                continue
                
            print(f"🔍 Scanning workspace root: {workspace_root}")
            
            for user_dir in workspace_root.iterdir():
                if not user_dir.is_dir():
                    continue
                if only_user and user_dir.name != only_user:
                    continue
                    
                print(f"  Found user directory: {user_dir.name}")
                audits_dir = user_dir / "audits"
                if not audits_dir.exists():
                    print(f"    No audits directory for user {user_dir.name}")
                    continue
                    
                print(f"    Scanning audits for user: {user_dir.name}")
                    
                for audit_dir in audits_dir.iterdir():
                    if not audit_dir.is_dir():
                        continue
                        
                    print(f"  Found user audit: {audit_dir.name} for user {user_dir.name}")
                    audit_data = self._index_user_audit(audit_dir, user_dir.name)
                    if audit_data:
                        print(f"  ✓ Indexed user audit: {audit_data['ts']} status={audit_data['status']}")
                        runs.append(audit_data)
                    else:
                        print(f"  ✗ Failed to index user audit: {audit_dir.name}")
        
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
            
            # Check for test generation results
            tests_file = run_dir / "tests.json"
            has_tests = tests_file.exists()
            test_count = 0
            if has_tests:
                try:
                    with open(tests_file) as f:
                        tests_data = json.load(f)
                        test_count = len(tests_data.get('tests', []))
                except:
                    has_tests = False
            
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
                'has_tests': has_tests,
                'test_count': test_count,
                'status': 'completed',
                'risk_file': str(risk_file),
                'report_html': str(report_html),
                'report_pdf': str(report_pdf) if report_pdf.exists() else None,
                'timestamp': datetime.now().isoformat() # Add timestamp for sorting
            }
            
        except Exception as e:
            print(f"Error indexing run {run_dir}: {e}")
            return None
    
    def _index_user_audit(self, audit_dir: Path, user_name: str) -> Optional[Dict[str, Any]]:
        """Index a user audit (including in-progress ones)."""
        try:
            audit_id = audit_dir.name
            
            # Check for status file
            status_file = audit_dir / f"{audit_id}_status.json"
            metadata_file = audit_dir / f"{audit_id}_metadata.json"
            
            if not status_file.exists() and not metadata_file.exists():
                return None
            
            # Load status or metadata
            audit_data = {}
            if status_file.exists():
                with open(status_file) as f:
                    audit_data = json.load(f)
            elif metadata_file.exists():
                with open(metadata_file) as f:
                    audit_data = json.load(f)
            
            status = audit_data.get('status', 'unknown')
            phase = audit_data.get('phase', 'unknown')
            
            # For completed audits, try to get more detailed info
            if status == 'completed':
                result_path = audit_data.get('result_path')
                if result_path:
                    result_dir = Path(result_path)
                    if result_dir.exists():
                        return self._index_run(result_dir, f'user-{user_name}')
            
            # For in-progress or failed audits, return basic info
            return {
                'ts': audit_id,
                'path': str(audit_dir),
                'grade': 'Pending' if status in ['running', 'cloning'] else 'Failed',
                'overall': 0.0,
                'delta': 0.0,
                'kind': 'evm',  # Default assumption
                'id': audit_id,
                'has_pdf': False,
                'has_html': False,
                'has_tests': False,
                'test_count': 0,
                'status': status,
                'phase': phase,
                'user': user_name,
                'created_at': audit_data.get('created_at', ''),
                'updated_at': audit_data.get('updated_at', ''),
                'error': audit_data.get('error', ''),
                'timestamp': audit_data.get('updated_at', audit_data.get('created_at', datetime.now().isoformat()))
            }
            
        except Exception as e:
            print(f"Error indexing user audit {audit_dir}: {e}")
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
