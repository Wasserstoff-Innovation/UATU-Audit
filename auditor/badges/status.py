"""
Status badge system for UatuAudit - Comprehensive risk assessment badges.
"""

from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

# Status badge definitions with exact colors and conditions
STATUS_BADGES = {
    # Primary badges (evaluate in order)
    "critical": {
        "label": "Critical",
        "color": "#d32f2f",
        "description": "Critical security issues detected",
        "priority": 1
    },
    "dangerous": {
        "label": "Dangerous",
        "color": "#f57c00",
        "description": "High risk or multiple test failures",
        "priority": 2
    },
    "needs_fixes": {
        "label": "Needs Fixes",
        "color": "#fbc02d",
        "description": "Some tests fail or EoP issues detected",
        "priority": 3
    },
    "passed_audit": {
        "label": "Passed Audit",
        "color": "#0288d1",
        "description": "Acceptable risk, tests pass",
        "priority": 4
    },
    "ready_to_go": {
        "label": "Ready to Go",
        "color": "#2e7d32",
        "description": "Low risk, all tests pass, no STRIDE issues",
        "priority": 5
    },
    
    # Secondary badges (can be combined with primary)
    "trend_worsening": {
        "label": "Trend Worsening",
        "color": "#f57c00",
        "description": "Risk increasing vs baseline",
        "priority": 6
    },
    "static_failed": {
        "label": "Static Failed",
        "color": "#6e7781",
        "description": "Slither crashed or timed out",
        "priority": 7
    },
    "tests_incomplete": {
        "label": "Tests Incomplete",
        "color": "#6e7781",
        "description": "No tests generated or runner failed",
        "priority": 8
    },
    "gas_heavy": {
        "label": "Gas Heavy",
        "color": "#6e7781",
        "description": "Any test gas exceeds threshold",
        "priority": 9
    },
    "coverage_low": {
        "label": "Coverage Low",
        "color": "#6e7781",
        "description": "Generated journeys < public/external functions",
        "priority": 10
    },
    "llm_assisted": {
        "label": "LLM Assisted",
        "color": "#7b1fa2",
        "description": "AI-powered analysis enabled",
        "priority": 11
    }
}

def determine_status_badges(
    risk_summary: Dict[str, Any],
    test_runs: Dict[str, Any] = None,
    eop_results: Dict[str, Any] = None,
    llm_enabled: bool = False,
    static_mode: str = "host",
    baseline_age_days: int = None,
    gas_threshold: int = 300000
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Determine applicable status badges based on audit results.
    
    Returns tuple of (primary_badge, secondary_badges).
    Primary badge is one of the first 5; secondary badges can be combined.
    """
    primary_badge = None
    secondary_badges = []
    
    # Extract key metrics
    overall = risk_summary.get('overall', 0.0)
    grade = risk_summary.get('grade', 'Unknown')
    delta = risk_summary.get('delta_overall', 0.0)
    
    # Test status
    tests_failed = 0
    tests_total = 0
    if test_runs:
        for run in test_runs.get('runs', []):
            tests_failed += run.get('failed', 0)
            tests_total += run.get('total', 0)
    
    # EoP status
    eop_issues = False
    if eop_results:
        eop_issues = any(
            item.get('status') == 'failed' 
            for item in eop_results.get('items', [])
        )
    
    # Gas consumption check
    gas_heavy = False
    if test_runs:
        for run in test_runs.get('runs', []):
            for test in run.get('tests', []):
                if test.get('gas_used', 0) > gas_threshold:
                    gas_heavy = True
                    break
    
    # STRIDE categories check (for Ready to Go)
    stride_flagged = False
    if risk_summary.get('by_function'):
        for func_data in risk_summary['by_function'].values():
            if func_data.get('evidence', {}).get('stride_categories'):
                stride_flagged = True
                break
    
    # Primary badge determination (evaluate in order)
    if overall >= 85 or (tests_failed > 0 and overall >= 70):
        primary_badge = STATUS_BADGES['critical']
    elif overall >= 70:
        primary_badge = STATUS_BADGES['dangerous']
    elif overall >= 50 or eop_issues:
        primary_badge = STATUS_BADGES['needs_fixes']
    elif overall < 50 and tests_failed == 0:
        primary_badge = STATUS_BADGES['passed_audit']
    elif overall < 25 and tests_failed == 0 and not stride_flagged:
        primary_badge = STATUS_BADGES['ready_to_go']
    else:
        primary_badge = STATUS_BADGES['passed_audit']  # fallback
    
    # Secondary badges
    if delta > 5:
        secondary_badges.append(STATUS_BADGES['trend_worsening'])
    
    if static_mode != "host" or (test_runs and not test_runs.get('slither_success', True)):
        secondary_badges.append(STATUS_BADGES['static_failed'])
    
    if not test_runs or tests_total == 0:
        secondary_badges.append(STATUS_BADGES['tests_incomplete'])
    
    if gas_heavy:
        secondary_badges.append(STATUS_BADGES['gas_heavy'])
    
    # Coverage check (simplified - would need journey metadata)
    # if generated_journeys < public_external_functions:
    #     secondary_badges.append(STATUS_BADGES['coverage_low'])
    
    if llm_enabled:
        secondary_badges.append(STATUS_BADGES['llm_assisted'])
    
    return primary_badge, secondary_badges

def get_primary_status(primary_badge: Dict[str, Any], secondary_badges: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get the primary status badge."""
    return primary_badge if primary_badge else STATUS_BADGES['passed_audit']

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

def render_status_badges(primary_badge: Dict[str, Any], secondary_badges: List[Dict[str, Any]] = None) -> str:
    """Render primary and secondary status badges as HTML."""
    html = render_status_badge(primary_badge, "large")
    
    if secondary_badges:
        html += '<div style="margin-top: 0.5cm;">'
        for badge in secondary_badges:
            html += render_status_badge(badge, "normal")
            html += ' '
        html += '</div>'
    
    return html

def get_status_summary(primary_badge: Dict[str, Any], secondary_badges: List[Dict[str, Any]] = None) -> str:
    """Get a human-readable summary of status badges."""
    if not primary_badge:
        return "Status assessment incomplete"
    
    summary = f"Primary: {primary_badge['label']}"
    if primary_badge.get('description'):
        summary += f" - {primary_badge['description']}"
    
    if secondary_badges:
        summary += f". Additional: {', '.join(b['label'] for b in secondary_badges)}"
    
    return summary
