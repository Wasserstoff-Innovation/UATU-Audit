"""
Dashboard views for UatuAudit.
"""

import os
from datetime import datetime
from pathlib import Path
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from .security import get_current_user
from .run_indexer import RunIndexer

# Setup templates
templates = Jinja2Templates(directory="auditor/dashboard/templates")

# Setup run indexer
indexer = RunIndexer()

def get_grade_color(grade: str) -> str:
    """Get color for risk grade."""
    colors = {
        "Critical": "#d32f2f",
        "High": "#f57c00", 
        "Medium": "#fbc02d",
        "Low": "#0288d1",
        "Info": "#2e7d32",
        "Unknown": "#6e7781"
    }
    return colors.get(grade, "#6e7781")

async def landing_page(request: Request):
    """Landing page with Uatu branding and wallet integration."""
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "year": datetime.now().year,
        # Environment variables for frontend configuration
        "api_base_url": os.getenv("API_BASE_URL", "http://localhost:8000"),
        "github_client_id": os.getenv("GITHUB_CLIENT_ID", ""),
        "github_redirect_uri": os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8080/auth/github"),
        "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:8080"),
        "audit_price_usdc": int(os.getenv("DEFAULT_AUDIT_PRICE_USDC", "200")),
        "max_audit_time": int(os.getenv("MAX_AUDIT_TIME_SECONDS", "30")),
        "environment": os.getenv("ENVIRONMENT", "production"),
        "debug": os.getenv("DEBUG", "false").lower() == "true"
    })

async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {
        "request": request
    })

async def github_auth(request: Request):
    """Initiate GitHub OAuth."""
    from .auth import github_login
    return await github_login(request)

async def auth_callback(request: Request):
    """Handle GitHub OAuth callback."""
    from .auth import github_callback as gh_callback
    return await gh_callback(request)

async def logout(request: Request):
    """Logout user."""
    from .security import clear_user_session
    clear_user_session(request)
    return RedirectResponse(url="/login")

async def runs_page(request: Request):
    """Main runs listing page - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to login if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    
    # Get filter parameters
    grade_filter = request.query_params.get("grade", "")
    kind_filter = request.query_params.get("kind", "")
    search_query = request.query_params.get("search", "")
    
    # Get all runs
    runs = indexer.scan_runs()
    
    # Apply filters
    filtered_runs = runs
    if grade_filter:
        filtered_runs = [r for r in filtered_runs if r['grade'] == grade_filter]
    if kind_filter:
        filtered_runs = [r for r in filtered_runs if r['kind'] == kind_filter]
    if search_query:
        filtered_runs = [r for r in filtered_runs if search_query.lower() in r['id'].lower()]
    
    # Get unique values for filters
    grades = list(set(r['grade'] for r in runs))
    kinds = list(set(r['kind'] for r in runs))
    
    return templates.TemplateResponse("runs.html", {
        "request": request,
        "user": user,
        "runs": filtered_runs,
        "grades": grades,
        "kinds": kinds,
        "grade_filter": grade_filter,
        "kind_filter": kind_filter,
        "search_query": search_query,
        "get_grade_color": get_grade_color
    })

async def run_detail(request: Request, ts: str):
    """Individual run detail page - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to login if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    
    run = indexer.get_run_by_ts(ts)
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return templates.TemplateResponse("run_detail.html", {
        "request": request,
        "user": user,
        "run": run,
        "get_grade_color": get_grade_color
    })

async def portfolio_page(request: Request):
    """Portfolio overview page - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to login if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    
    portfolio = indexer.scan_portfolio()
    
    if not portfolio:
        return templates.TemplateResponse("portfolio.html", {
            "request": request,
            "user": user,
            "portfolio": None,
            "error": "No portfolio data found"
        })
    
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "user": user,
        "portfolio": portfolio,
        "get_grade_color": get_grade_color
    })

async def download_pdf(request: Request, ts: str):
    """Download PDF for a run - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to login if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=302)
    
    run = indexer.get_run_by_ts(ts)
    if not run or not run.get('report_pdf'):
        raise HTTPException(status_code=404, detail="PDF not found")
    
    pdf_path = Path(run['report_pdf'])
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    return FileResponse(
        pdf_path,
        media_type='application/pdf',
        filename=f"audit-{ts}.pdf"
    )

async def download_portfolio_pdf(request: Request):
    """Download portfolio PDF."""
    portfolio = indexer.scan_portfolio()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    pdf_path = Path(portfolio.get('portfolio_pdf', ''))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Portfolio PDF not found")
    
    return FileResponse(
        pdf_path,
        media_type='application/pdf',
        filename=f"portfolio-{portfolio['ts']}.pdf"
    )

async def download_csv(request: Request):
    """Download portfolio CSV."""
    portfolio = indexer.scan_portfolio()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    
    csv_path = Path(portfolio.get('portfolio_csv', ''))
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Portfolio CSV not found")
    
    return FileResponse(
        csv_path,
        media_type='text/csv',
        filename=f"portfolio-{portfolio['ts']}.csv"
    )

async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
