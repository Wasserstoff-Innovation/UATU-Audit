"""
Dashboard views for UatuAudit.
"""

import os
import subprocess
import asyncio
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from fastapi import Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
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
        "github_redirect_uri": os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8080/auth/callback"),
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
                import json
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
