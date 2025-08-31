"""
Dashboard views and routes for UatuAudit.
"""

import os
from pathlib import Path
from typing import Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from .security import login_required, get_current_user, set_user_session, clear_user_session
from .auth import github_login, github_callback
from .run_indexer import RunIndexer

# Setup templates
templates = Jinja2Templates(directory="auditor/dashboard/templates")

# Setup run indexer
indexer = RunIndexer(cache_ttl=int(os.getenv('DASHBOARD_CACHE_TTL', '10')))

def get_grade_color(grade: str) -> str:
    """Get color for risk grade."""
    colors = {
        "Critical": "#d32f2f",
        "High": "#f57c00",
        "Medium": "#fbc02d",
        "Low": "#0288d1",
        "Info": "#2e7d32",
    }
    return colors.get(grade, "#6e7781")

async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})

async def github_auth(request: Request):
    """Initiate GitHub OAuth."""
    return await github_login(request)

async def auth_callback(request: Request):
    """Handle OAuth callback."""
    user_info = await github_callback(request)
    if user_info:
        set_user_session(request, user_info)
        return templates.TemplateResponse("redirect.html", {
            "request": request,
            "message": "Login successful! Redirecting...",
            "redirect_url": "/"
        })
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Authentication failed. Please try again."
        })

async def logout(request: Request):
    """Logout user."""
    clear_user_session(request)
    return templates.TemplateResponse("redirect.html", {
        "request": request,
        "message": "Logged out successfully! Redirecting...",
        "redirect_url": "/login"
    })

@login_required
async def runs_page(request: Request):
    """Main runs listing page."""
    user = get_current_user(request)
    runs = indexer.scan_runs()
    
    # Apply filters
    grade_filter = request.query_params.get('grade', '')
    kind_filter = request.query_params.get('kind', '')
    search_query = request.query_params.get('search', '')
    
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

@login_required
async def run_detail(request: Request, ts: str):
    """Individual run detail page."""
    user = get_current_user(request)
    run = indexer.get_run_by_ts(ts)
    
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return templates.TemplateResponse("run_detail.html", {
        "request": request,
        "user": user,
        "run": run,
        "get_grade_color": get_grade_color
    })

@login_required
async def portfolio_page(request: Request):
    """Portfolio overview page."""
    user = get_current_user(request)
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

@login_required
async def download_pdf(request: Request, ts: str):
    """Download PDF for a run."""
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

@login_required
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

@login_required
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
    return {"status": "healthy", "service": "uatu-dashboard"}
