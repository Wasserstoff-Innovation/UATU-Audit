"""
Status badge system for UatuAudit - Comprehensive risk assessment badges.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# Status badge definitions
STATUS_BADGES = {
    "ready_to_go": {
        "label": "Ready to Go",
        "color": "#2e7d32",
        "description": "Low risk, all tests pass, no critical issues"
    },
    "passed_audit": {
        "label": "Passed Audit",
        "color": "#0288d1",
        "description": "Acceptable risk, tests pass"
    },
    "needs_fixes": {
        "label": "Needs Fixes",
        "description": "Some tests fail or EoP issues detected"
    },
    "dangerous": {
        "label": "Dangerous",
        "color": "#f57c00",
        "description": "High risk or multiple test failures"
    },
    "critical": {
        "label": "Critical",
        "color": "#d32f2f",
        "description": "Critical security issues detected"
    },
    "trend_worsening": {
        "label": "Trend Worsening",
        "color": "#f57c00",
        "description": "Risk increasing vs baseline"
    },
    "static_incomplete": {
        "label": "Static Incomplete",
        "color": "#6e7781",
        "description": "Static analysis not fully completed"
    },
    "tests_incomplete": {
        "label": "Tests Incomplete",
        "color": "#6e7781",
        "description": "Test execution not fully completed"
    },
    "llm_assisted": {
        "label": "LLM Assisted",
        "color": "#6f42c1",
        "description": "AI-powered analysis enabled"
    },
    "outdated_baseline": {
        "label": "Outdated Baseline",
        "color": "#6e7781",
        "description": "Baseline data is old"
    }
}

def determine_status_badges(
    risk_summary: Dict[str, Any],
    test_runs: Dict[str, Any] = None,
    eop_results: Dict[str, Any] = None,
    llm_enabled: bool = False,
    static_mode: str = "host",
    baseline_age_days: int = None
) -> List[Dict[str, Any]]:
    """
    Determine applicable status badges based on audit results.
    
    Returns list of badges in priority order (first is primary).
    """
    badges = []
    
    # Extract key metrics
    overall = risk_summary.get('overall', 0.0)
    grade = risk_summary.get('grade', 'Unknown')
    delta = risk_summary.get('delta_overall', 0.0)
    
    # Test status
    tests_passed = True
    if test_runs:
        for run in test_runs.get('runs', []):
            if run.get('failed', 0) > 0:
                tests_passed = False
                break
    
    # EoP status
    eop_issues = False
    if eop_results:
        eop_issues = any(
            item.get('status') == 'failed' 
            for item in eop_results.get('items', [])
        )
    
    # Primary status determination
    if (grade in ['Info', 'Low'] and 
        overall <= 25 and 
        tests_passed and 
        not eop_issues and 
        delta >= 0):
        badges.append(STATUS_BADGES['ready_to_go'])
    
    elif (grade in ['Info', 'Low', 'Medium'] and 
          overall <= 50 and 
          tests_passed):
        badges.append(STATUS_BADGES['passed_audit'])
    
    elif (grade in ['High', 'Critical'] or 
          overall > 75):
        badges.append(STATUS_BADGES['critical'])
    
    elif not tests_passed or eop_issues:
        badges.append(STATUS_BADGES['needs_fixes'])
    
    else:
        badges.append(STATUS_BADGES['dangerous'])
    
    # Secondary badges
    if delta > 5:  # Assuming MAX_DELTA = 5
        badges.append(STATUS_BADGES['trend_worsening'])
    
    if static_mode != "host":
        badges.append(STATUS_BADGES['static_incomplete'])
    
    if not test_runs or not tests_passed:
        badges.append(STATUS_BADGES['tests_incomplete'])
    
    if llm_enabled:
        badges.append(STATUS_BADGES['llm_assisted'])
    
    if baseline_age_days and baseline_age_days > 30:
        badges.append(STATUS_BADGES['outdated_baseline'])
    
    return badges

def get_primary_status(badges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get the primary (first) status badge."""
    return badges[0] if badges else STATUS_BADGES['passed_audit']

def render_status_badge(badge: Dict[str, Any], size: str = "normal") -> str:
    """Render a status badge as HTML."""
    color = badge.get('color', '#6e7781')
    label = badge.get('label', 'Unknown')
    
    if size == "large":
        style = f"""
        display: inline-block;
        padding: 1rem 2rem;
        background: {color};
        color: white;
        border-radius: 8px;
        font-size: 14pt;
        font-weight: 600;
        text-align: center;
        margin: 1rem 0;
        """
    else:
        style = f"""
        display: inline-block;
        padding: 0.5cm 1cm;
        background: {color};
        color: white;
        border-radius: 6px;
        font-size: 10pt;
        font-weight: 600;
        text-align: center;
        margin: 0.5cm 0;
        """
    
    return f'<span class="status-badge" style="{style}">{label}</span>'

def get_status_summary(badges: List[Dict[str, Any]]) -> str:
    """Get a human-readable summary of status badges."""
    if not badges:
        return "Status assessment incomplete"
    
    primary = badges[0]
    secondary = badges[1:] if len(badges) > 1 else []
    
    summary = f"Primary: {primary['label']}"
    if primary.get('description'):
        summary += f" - {primary['description']}"
    
    if secondary:
        summary += f". Additional: {', '.join(b['label'] for b in secondary)}"
    
    return summary
