"""
Dashboard views for the UatuAudit system.
"""

import os
import hashlib
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
import json

from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .security import get_current_user, set_user_session, clear_user_session

# Templates setup
templates = Jinja2Templates(directory="auditor/dashboard/templates")

# OAuth endpoints
async def github_auth(request: Request):
    """GitHub OAuth redirect."""
    return RedirectResponse(url="/onboarding/repos")

async def auth_callback(request: Request):
    """GitHub OAuth callback."""
    return RedirectResponse(url="/dashboard")

async def logout(request: Request):
    """Logout endpoint."""
    from .security import clear_user_session
    clear_user_session(request)
    return RedirectResponse(url="/")

async def runs_page(request: Request):
    """Main dashboard - shows projects instead of runs."""
    user = get_current_user(request)
    
    # Check for wallet authentication 
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        # Use GitHub user if available, otherwise fallback to Soneshwar
        if 'user' in request.session:
            session_user = request.session['user']
            if isinstance(session_user, dict) and session_user.get('login'):
                user = session_user.copy()
                user['wallet_address'] = request.session['wallet_address']
            else:
                user = {
                    'login': 'Soneshwar',
                    'email': None,
                    'name': f"User {request.session['wallet_address'][:8]}",
                    'wallet_address': request.session['wallet_address']
                }
        else:
            user = {
                'login': 'Soneshwar',
                'email': None, 
                'name': f"User {request.session['wallet_address'][:8]}",
                'wallet_address': request.session['wallet_address']
            }
    
    # If no user, redirect to landing page
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    # Get projects from workspace
    user_workspace = get_user_workspace(user.get('login', 'Soneshwar'))
    projects_dir = user_workspace / "projects"
    
    projects = []
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                project_info = {
                    'name': project_dir.name.replace('~', '/'),  # TribesByAstrix
                    'path': project_dir.name,  # For URLs
                    'branches': []
                }
                
                # Get branches
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            # Check if branch has source files
                            has_source = len(list(branch_dir.rglob("*.sol"))) > 0
                            # Check if branch has test cases
                            has_tests = len(list(branch_dir.rglob("test/*.sol"))) > 0 or len(list(branch_dir.rglob("tests/*.sol"))) > 0
                            
                            project_info['branches'].append({
                                'name': branch_dir.name,
                                'has_source': has_source,
                                'has_tests': has_tests
                            })
                
                projects.append(project_info)
    
    # Load project metadata if available
    for project in projects:
        project_json = projects_dir / project['path'] / 'project.json'
        if project_json.exists():
            try:
                with open(project_json, 'r') as f:
                    metadata = json.load(f)
                    project['repo_owner'] = metadata.get('repo_owner', 'unknown')
                    project['created_at'] = metadata.get('created_at', '')
            except Exception:
                pass
    
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "user": user,
        "projects": projects
    })

async def run_detail(request: Request, ts: str):
    """Run detail page with timeline and streaming logs."""
    user = get_current_user(request)
    
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("run_detail.html", {
        "request": request,
        "user": user,
        "ts": ts
    })

# Landing page
async def landing_page(request: Request):
    """Landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})

# Projects page
async def projects_page(request: Request):
    """Projects page."""
    return await runs_page(request)  # Use same logic as runs_page

# Portfolio page
async def portfolio_page(request: Request):
    """Portfolio page."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("portfolio.html", {
        "request": request,
        "user": user
    })

# Onboarding repos page
async def onboarding_repos(request: Request):
    """Repository onboarding page."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    return templates.TemplateResponse("onboarding_repos.html", {
        "request": request,
        "user": user
    })

# Utility functions
def get_user_workspace(user_login: str) -> Path:
    """Get the user's workspace directory."""
    workspace_root = Path(os.getenv("WORKSPACE_ROOT", "/Users/soneshwar/.uatu_audit/workspaces"))
    user_workspace = workspace_root / user_login
    user_workspace.mkdir(parents=True, exist_ok=True)
    return user_workspace

# API endpoints
async def api_github_repos(request: Request):
    """API endpoint to get GitHub repositories."""
    return JSONResponse({"repos": []})

async def api_github_branches(request: Request):
    """API endpoint to get GitHub branches."""
    return JSONResponse({"branches": []})

async def api_projects(request: Request):
    """API endpoint for projects data."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Return projects in the format expected by projects.html
    user_workspace = get_user_workspace(user.get('login', 'Soneshwar'))
    projects_dir = user_workspace / "projects"
    
    projects = []
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                project_info = {
                    'id': project_dir.name,
                    'owner_repo': project_dir.name.replace('~', '/'),
                    'branches': [],
                    'settings': {
                        'llm': 'gpt-4',
                        'journey_cap': 10,
                        'stress': 'medium'
                    }
                }
                
                # Get branches
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            project_info['branches'].append({
                                'name': branch_dir.name,
                                'last_run': None  # TODO: Get actual run data
                            })
                
                projects.append(project_info)
    
    return JSONResponse({"projects": projects})

async def setup_project(request: Request):
    """Setup project endpoint."""
    return RedirectResponse(url="/dashboard", status_code=302)

async def health_check(request: Request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})

# Stub endpoints for compatibility
async def download_pdf(request: Request, ts: str):
    """Download PDF endpoint."""
    return JSONResponse({"error": "PDF not found"}, status_code=404)

async def download_portfolio_pdf(request: Request):
    """Download portfolio PDF endpoint.""" 
    return JSONResponse({"error": "PDF not found"}, status_code=404)

async def download_csv(request: Request):
    """Download CSV endpoint."""
    return JSONResponse({"error": "CSV not found"}, status_code=404)

async def api_audit_status(request: Request):
    """API audit status endpoint."""
    return JSONResponse({"status": "idle"})

async def api_quick_status(request: Request):
    """API quick status endpoint."""
    return JSONResponse({"current_audit": None})

async def api_list_user_audits(request: Request):
    """API list user audits endpoint."""
    return JSONResponse({"audits": []})

async def api_run_status(request: Request, ts: str):
    """API run status endpoint."""
    return JSONResponse({"status": "unknown"})

async def api_run_logs(request: Request, ts: str):
    """API run logs endpoint."""
    return JSONResponse({"logs": [], "has_more": False})

async def api_project_runs(request: Request, owner_repo: str):
    """API project runs endpoint."""
    return JSONResponse({"runs": []})

async def test_endpoint(request: Request):
    """Test endpoint."""
    return JSONResponse({"message": "Test successful"})

async def test_oauth(request: Request):
    """Test OAuth endpoint.""" 
    return JSONResponse({"message": "OAuth test"})

async def debug_workspace(request: Request):
    """Debug workspace endpoint."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    workspace = get_user_workspace(user.get('login', 'demo'))
    return JSONResponse({
        "user": user,
        "workspace": str(workspace),
        "exists": workspace.exists()
    })