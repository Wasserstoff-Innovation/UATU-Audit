"""
Centralized logging system for UatuAudit.

Instead of scattered logs in every test folder, this provides:
1. Single log location per project/branch
2. Structured logging with timestamps and phases
3. Easy log retrieval for dashboard UI
4. Status tracking integration
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum

class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info" 
    WARN = "warn"
    ERROR = "error"

class AuditPhase(Enum):
    INIT = "init"
    CLONING = "cloning"
    ANALYSIS = "analysis"
    TEST_GEN = "test_generation"
    TESTING = "testing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"

class CentralizedLogger:
    """Centralized logger for audit runs."""
    
    def __init__(self, project_root: Path, branch: str, run_id: str):
        self.project_root = Path(project_root)
        self.branch = branch
        self.run_id = run_id
        self.log_dir = self.project_root / 'branches' / branch / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Main log file for this run
        self.log_file = self.log_dir / f"{run_id}.jsonl"
        self.status_file = self.log_dir / f"{run_id}_status.json"
        
        # Initialize status
        self.current_status = {
            "run_id": run_id,
            "branch": branch,
            "phase": AuditPhase.INIT.value,
            "status": "starting",
            "progress_pct": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "logs_file": str(self.log_file)
        }
        self._write_status()
    
    def _write_status(self):
        """Write current status to status file."""
        self.current_status["updated_at"] = datetime.utcnow().isoformat()
        with open(self.status_file, 'w') as f:
            json.dump(self.current_status, f, indent=2)
    
    def log(self, level: LogLevel, phase: AuditPhase, message: str, 
            meta: Optional[Dict[str, Any]] = None):
        """Write a log entry."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.value,
            "phase": phase.value,
            "message": message,
            "meta": meta or {}
        }
        
        # Append to log file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def update_phase(self, phase: AuditPhase, progress_pct: int = None, 
                    status: str = None, message: str = None):
        """Update the current phase and status."""
        self.current_status["phase"] = phase.value
        if progress_pct is not None:
            self.current_status["progress_pct"] = progress_pct
        if status:
            self.current_status["status"] = status
        
        self._write_status()
        
        if message:
            self.log(LogLevel.INFO, phase, message)
    
    def error(self, phase: AuditPhase, message: str, error: Exception = None):
        """Log an error and update status."""
        meta = {}
        if error:
            meta["error_type"] = type(error).__name__
            meta["error_details"] = str(error)
        
        self.log(LogLevel.ERROR, phase, message, meta)
        self.update_phase(phase, status="error")
    
    def complete(self, message: str = "Audit completed successfully"):
        """Mark audit as completed."""
        self.update_phase(AuditPhase.COMPLETED, 100, "completed", message)

def get_centralized_logger(project_root: Path, branch: str, run_id: str) -> CentralizedLogger:
    """Get a centralized logger instance."""
    return CentralizedLogger(project_root, branch, run_id)

def get_run_logs(project_root: Path, branch: str, run_id: str, 
                offset: int = 0, limit: int = 500) -> Dict[str, Any]:
    """Get logs for a specific run with pagination."""
    log_dir = Path(project_root) / 'branches' / branch / 'logs'
    log_file = log_dir / f"{run_id}.jsonl"
    
    if not log_file.exists():
        return {"logs": [], "next_offset": offset}
    
    logs = []
    current_offset = 0
    next_offset = offset
    
    with open(log_file, 'r') as f:
        for line in f:
            if current_offset < offset:
                current_offset += len(line.encode('utf-8'))
                continue
            
            if len(logs) >= limit:
                break
                
            try:
                logs.append(json.loads(line.strip()))
                next_offset = current_offset + len(line.encode('utf-8'))
                current_offset = next_offset
            except json.JSONDecodeError:
                continue
    
    return {
        "logs": logs,
        "next_offset": next_offset,
        "total_lines": len(logs)
    }

def get_run_status(project_root: Path, branch: str, run_id: str) -> Optional[Dict[str, Any]]:
    """Get status for a specific run."""
    log_dir = Path(project_root) / 'branches' / branch / 'logs'
    status_file = log_dir / f"{run_id}_status.json"
    
    if not status_file.exists():
        return None
    
    try:
        with open(status_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None

def list_project_runs(project_root: Path, branch: str) -> List[Dict[str, Any]]:
    """List all runs for a project branch."""
    log_dir = Path(project_root) / 'branches' / branch / 'logs'
    
    if not log_dir.exists():
        return []
    
    runs = []
    for status_file in log_dir.glob("*_status.json"):
        run_id = status_file.stem.replace("_status", "")
        status = get_run_status(project_root, branch, run_id)
        if status:
            runs.append(status)
    
    # Sort by creation time, newest first
    runs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return runs