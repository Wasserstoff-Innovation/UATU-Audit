"""
Centralized color definitions for the contract auditor.
Single source of truth for grade colors across badges, sparklines, and reports.
"""

GRADE_COLORS = {
    "Critical": "#d32f2f",
    "High": "#f57c00", 
    "Medium": "#fbc02d",
    "Low": "#0288d1",
    "Info": "#2e7d32",
}

def get_grade_color(grade: str) -> str:
    """Get color for a given risk grade."""
    return GRADE_COLORS.get(grade or "", "#6e7781")  # fallback to gray

def get_grade_colors() -> dict:
    """Get the complete grade color mapping."""
    return GRADE_COLORS.copy()
