"""
PDF report generation for UatuAudit using WeasyPrint.
"""

import os
from pathlib import Path
from typing import Optional
from weasyprint import HTML, CSS

def render_pdf(html_path: str, pdf_path: str, base_url: str = None) -> bool:
    """Render HTML report to PDF using WeasyPrint."""
    try:
        # Ensure output directory exists
        pdf_path = Path(pdf_path)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set base URL for relative paths
        if base_url is None:
            base_url = str(Path(html_path).parent)
        
        # Load HTML and CSS
        html = HTML(filename=html_path, base_url=base_url)
        css_path = Path(__file__).parent / "print.css"
        
        if css_path.exists():
            css = CSS(filename=str(css_path))
            html.write_pdf(pdf_path, stylesheets=[css])
        else:
            # Fallback without custom CSS
            html.write_pdf(pdf_path)
        
        return True
        
    except Exception as e:
        print(f"Error rendering PDF: {e}")
        return False

def render_portfolio_pdf(html_path: str, pdf_path: str, base_url: str = None) -> bool:
    """Render portfolio HTML report to PDF."""
    return render_pdf(html_path, pdf_path, base_url)

def get_pdf_path(html_path: str) -> str:
    """Get PDF path for a given HTML path."""
    html_path = Path(html_path)
    return str(html_path.with_suffix('.pdf'))

def ensure_pdf_exists(html_path: str, base_url: str = None) -> Optional[str]:
    """Ensure PDF exists, generate if it doesn't."""
    html_path = Path(html_path)
    pdf_path = get_pdf_path(html_path)
    
    if not Path(pdf_path).exists():
        if render_pdf(str(html_path), pdf_path, base_url):
            return pdf_path
        else:
            return None
    
    return pdf_path
