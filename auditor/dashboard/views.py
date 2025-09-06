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
        # Use GitHub user if available, otherwise create wallet-specific user
        if 'user' in request.session:
            session_user = request.session['user']
            if isinstance(session_user, dict) and session_user.get('login'):
                user = session_user.copy()
                user['wallet_address'] = request.session['wallet_address']
            else:
                user = {
                    'login': f"wallet_{request.session['wallet_address'][:8]}",
                    'email': None,
                    'name': f"User {request.session['wallet_address'][:8]}",
                    'wallet_address': request.session['wallet_address']
                }
        else:
            user = {
                'login': f"wallet_{request.session['wallet_address'][:8]}",
                'email': None, 
                'name': f"User {request.session['wallet_address'][:8]}",
                'wallet_address': request.session['wallet_address']
            }
    
    # If no user, redirect to landing page
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    # Get projects from workspace
    user_workspace = get_user_workspace(user.get('login'))
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
                            # Count contract files (not all source files)
                            contract_files = len(list(branch_dir.rglob("contracts/*.sol")))
                            if contract_files == 0:
                                contract_files = len(list(branch_dir.rglob("*.sol")))
                                
                            # Check if branch has test cases
                            test_count = len(list(branch_dir.rglob("test/*.sol"))) + len(list(branch_dir.rglob("tests/*.sol")))
                            
                            project_info['branches'].append({
                                'name': branch_dir.name,
                                'contract_count': contract_files,
                                'test_count': test_count
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
        "show_back_button": False,
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
    user = get_current_user(request)
    
    # Check for wallet authentication 
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        # Use GitHub user if available, otherwise create wallet-specific user
        if 'user' in request.session:
            session_user = request.session['user']
            if isinstance(session_user, dict) and session_user.get('login'):
                user = session_user.copy()
                user['wallet_address'] = request.session['wallet_address']
            else:
                user = {
                    'login': f"wallet_{request.session['wallet_address'][:8]}",
                    'email': None,
                    'name': f"User {request.session['wallet_address'][:8]}",
                    'wallet_address': request.session['wallet_address']
                }
        else:
            user = {
                'login': f"wallet_{request.session['wallet_address'][:8]}",
                'email': None, 
                'name': f"User {request.session['wallet_address'][:8]}",
                'wallet_address': request.session['wallet_address']
            }
    
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "user": user,
        "show_back_button": False
    })

# Projects page
async def projects_page(request: Request):
    """Projects page."""
    return await runs_page(request)  # Use same logic as runs_page

# GitHub connect page
async def github_connect_page(request: Request):
    """GitHub connect page."""
    user = get_current_user(request)
    
    # Check for wallet authentication 
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        # Use GitHub user if available, otherwise create wallet-specific user
        if 'user' in request.session:
            session_user = request.session['user']
            if isinstance(session_user, dict) and session_user.get('login'):
                user = session_user.copy()
                user['wallet_address'] = request.session['wallet_address']
            else:
                user = {
                    'login': f"wallet_{request.session['wallet_address'][:8]}",
                    'email': None,
                    'name': f"User {request.session['wallet_address'][:8]}",
                    'wallet_address': request.session['wallet_address']
                }
        else:
            user = {
                'login': f"wallet_{request.session['wallet_address'][:8]}",
                'email': None, 
                'name': f"User {request.session['wallet_address'][:8]}",
                'wallet_address': request.session['wallet_address']
            }
    
    return templates.TemplateResponse("github_connect.html", {
        "request": request,
        "user": user,
        "show_back_button": True,
        "back_url": "/"
    })

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
    
    # Check for wallet authentication (same as other endpoints)
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        if 'user' in request.session:
            session_user = request.session['user']
            if isinstance(session_user, dict) and session_user.get('login'):
                user = session_user.copy()
                user['wallet_address'] = wallet_address
            else:
                user = {
                    'login': f"wallet_{wallet_address[:8]}",  # Unique per wallet instead of hardcoded
                    'email': None,
                    'name': f"Wallet User {wallet_address[:8]}",
                    'wallet_address': wallet_address
                }
        else:
            user = {
                'login': f"wallet_{wallet_address[:8]}",  # Unique per wallet instead of hardcoded
                'email': None, 
                'name': f"Wallet User {wallet_address[:8]}",
                'wallet_address': wallet_address
            }
    
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    # Return projects in the format expected by projects.html
    user_workspace = get_user_workspace(user.get('login'))
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
    # Test authentication
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if user:
        workspace = get_user_workspace(user.get('login'))
        return JSONResponse({
            "message": "Authentication successful",
            "user": user,
            "workspace": str(workspace)
        })
    else:
        return JSONResponse({"message": "Not authenticated", "session": dict(request.session)})

async def test_oauth(request: Request):
    """Test OAuth endpoint.""" 
    return JSONResponse({"message": "OAuth test"})

# Project navigation pages
async def project_detail(request: Request, project_name: str):
    """Project detail page showing branches."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    # Get project directory
    user_workspace = get_user_workspace(user.get('login'))
    project_dir = user_workspace / "projects" / project_name
    
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_info = {
        'name': project_name.replace('~', '/'),
        'path': project_name,
        'branches': []
    }
    
    # Get branches
    branches_dir = project_dir / "branches"
    if branches_dir.exists():
        for branch_dir in branches_dir.iterdir():
            if branch_dir.is_dir():
                # Count contract files properly
                contract_count = len(list(branch_dir.rglob("contracts/*.sol")))
                if contract_count == 0:
                    contract_count = len(list(branch_dir.rglob("*.sol")))
                
                # Count test files
                test_count = len(list(branch_dir.rglob("test/*.sol"))) + len(list(branch_dir.rglob("tests/*.sol")))
                
                project_info['branches'].append({
                    'name': branch_dir.name,
                    'source_count': contract_count,
                    'test_count': test_count
                })
    
    return templates.TemplateResponse("project_detail.html", {
        "request": request,
        "user": user,
        "project": project_info,
        "show_back_button": True,
        "back_url": "/projects"
    })

async def debug_workspace(request: Request):
    """Debug workspace endpoint."""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    workspace = get_user_workspace(user.get('login'))
    return JSONResponse({
        "user": user,
        "workspace": str(workspace),
        "exists": workspace.exists()
    })

# Branch detail page
async def branch_detail(request: Request, project_name: str, branch_name: str):
    """Branch detail page showing test cases."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return RedirectResponse(url="/", status_code=302)
    
    # Get branch directory
    user_workspace = get_user_workspace(user.get('login'))
    branch_dir = user_workspace / "projects" / project_name / "branches" / branch_name
    
    if not branch_dir.exists():
        raise HTTPException(status_code=404, detail="Branch not found")
    
    project_info = {
        'name': project_name.replace('~', '/'),
        'path': project_name
    }
    
    branch_info = {
        'name': branch_name,
        'project': project_info
    }
    
    # Get test files
    tests = []
    test_dir = branch_dir / "test"
    if test_dir.exists():
        for test_file in test_dir.glob("*.sol"):
            tests.append({
                'name': test_file.stem,
                'file_path': str(test_file.relative_to(branch_dir)),
                'full_path': str(test_file)
            })
    
    return templates.TemplateResponse("branch_detail.html", {
        "request": request,
        "user": user,
        "project": project_info,
        "branch": branch_info,
        "tests": tests
    })

# Test case API endpoints
async def api_test_save(request: Request):
    """API endpoint to save a test case."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        body = await request.json()
        project_name = body.get('project')
        branch_name = body.get('branch')
        test_name = body.get('name')
        test_code = body.get('code')
        existing_test = body.get('existing')
        
        if not all([project_name, branch_name, test_name, test_code]):
            return JSONResponse({"error": "Missing required fields"}, status_code=400)
        
        # Get test directory
        user_workspace = get_user_workspace(user.get('login'))
        test_dir = user_workspace / "projects" / project_name / "branches" / branch_name / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Save test file
        test_file = test_dir / f"{test_name}.sol"
        with open(test_file, 'w') as f:
            f.write(test_code)
        
        return JSONResponse({"success": True, "message": "Test saved successfully"})
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_test_run(request: Request):
    """API endpoint to run a test case."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        body = await request.json()
        project_name = body.get('project')
        branch_name = body.get('branch')
        test_name = body.get('test')
        
        if not all([project_name, branch_name, test_name]):
            return JSONResponse({"error": "Missing required fields"}, status_code=400)
        
        # TODO: Implement actual test runner integration
        # For now, just return success
        return JSONResponse({
            "success": True, 
            "message": f"Test {test_name} started",
            "status": "running"
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_test_delete(request: Request):
    """API endpoint to delete a test case."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        body = await request.json()
        project_name = body.get('project')
        branch_name = body.get('branch')
        test_name = body.get('test')
        
        if not all([project_name, branch_name, test_name]):
            return JSONResponse({"error": "Missing required fields"}, status_code=400)
        
        # Get test file
        user_workspace = get_user_workspace(user.get('login'))
        test_file = user_workspace / "projects" / project_name / "branches" / branch_name / "test" / f"{test_name}.sol"
        
        if test_file.exists():
            test_file.unlink()
            return JSONResponse({"success": True, "message": "Test deleted successfully"})
        else:
            return JSONResponse({"error": "Test file not found"}, status_code=404)
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Automated audit API endpoint
async def api_audit_run(request: Request):
    """API endpoint to run automated AI audit for a specific branch."""
    user = get_current_user(request)
    
    # Check for wallet authentication
    if not user and request.session.get('authenticated') and request.session.get('wallet_address'):
        wallet_address = request.session['wallet_address']
        user = {
            'login': f"wallet_{wallet_address[:8]}",
            'email': None,
            'name': f"Wallet User {wallet_address[:8]}",
            'wallet_address': wallet_address
        }
    
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)
    
    try:
        body = await request.json()
        project_name = body.get('project')
        branch_name = body.get('branch')
        
        if not all([project_name, branch_name]):
            return JSONResponse({"error": "Missing project or branch"}, status_code=400)
        
        # Import audit functions from the existing audit system
        from ..runners.forge_runner import run_audit_from_local_project
        from datetime import datetime
        import uuid
        
        # Generate audit ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audit_id = f"{project_name}_{branch_name}_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Get project directory
        user_workspace = get_user_workspace(user.get('login'))
        project_dir = user_workspace / "projects" / project_name / "branches" / branch_name
        
        if not project_dir.exists():
            return JSONResponse({"error": "Project branch not found"}, status_code=404)
        
        # Run the automated audit in background
        background_tasks = BackgroundTasks()
        background_tasks.add_task(
            run_audit_from_local_project,
            str(project_dir),
            audit_id,
            user.get('login')
        )
        
        # Store audit info in session
        request.session['current_audit'] = {
            'id': audit_id,
            'project': project_name,
            'branch': branch_name,
            'user': user.get('login'),
            'status': 'starting',
            'created_at': datetime.now().isoformat()
        }
        
        return JSONResponse({
            "success": True,
            "audit_id": audit_id,
            "message": "AI audit started successfully"
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)