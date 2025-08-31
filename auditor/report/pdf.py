"""
PDF generation for UatuAudit reports.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader

def render_letterhead(context: Dict[str, Any], out_pdf: Path, base_url: Path) -> bool:
    """
    Render a professional PDF with letterhead and watermark.
    
    Args:
        context: Template context data
        out_pdf: Output PDF path
        out_pdf: Base URL for static assets
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Setup Jinja2 environment
        template_dir = Path(__file__).resolve().parent.parent / "templates" / "pdf"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("letterhead.html.j2")
        
        # Render HTML
        html_output = template.render(**context)
        
        # Try to generate PDF with WeasyPrint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            # Load CSS
            css_file = Path(__file__).resolve().parent / "print-letter.css"
            if css_file.exists():
                css = CSS(filename=str(css_file))
            else:
                css = None
            
            # Generate PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=html_output, base_url=str(base_url))
            
            html_doc.write_pdf(
                out_pdf,
                stylesheets=[css] if css else None,
                font_config=font_config
            )
            
            return True
            
        except ImportError:
            print("⚠️  WeasyPrint not available, saving HTML instead")
            # Fallback to HTML if WeasyPrint not available
            html_path = out_pdf.with_suffix('.html')
            html_path.write_text(html_output)
            return False
            
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return False

def render_standard_pdf(context: Dict[str, Any], out_pdf: Path, base_url: Path) -> bool:
    """
    Render the standard PDF template.
    
    Args:
        context: Template context data
        out_pdf: Output PDF path
        base_url: Base URL for static assets
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Setup Jinja2 environment
        template_dir = Path(__file__).resolve().parent.parent / "templates" / "pdf"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("report.html.j2")
        
        # Render HTML
        html_output = template.render(**context)
        
        # Try to generate PDF with WeasyPrint
        try:
            from weasyprint import HTML, CSS
            from weasyprint.text.fonts import FontConfiguration
            
            # Load CSS
            css_file = Path(__file__).resolve().parent / "print.css"
            if css_file.exists():
                css = CSS(filename=str(css_file))
            else:
                css = None
            
            # Generate PDF
            font_config = FontConfiguration()
            html_doc = HTML(string=html_output, base_url=str(base_url))
            
            html_doc.write_pdf(
                out_pdf,
                stylesheets=[css] if css else None,
                font_config=font_config
            )
            
            return True
            
        except ImportError:
            print("⚠️  WeasyPrint not available, saving HTML instead")
            # Fallback to HTML if WeasyPrint not available
            html_path = out_pdf.with_suffix('.html')
            html_path.write_text(html_output)
            return False
            
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return False
