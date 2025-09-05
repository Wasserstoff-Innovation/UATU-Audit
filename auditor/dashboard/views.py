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
    """Main runs listing page - allows unauthenticated access."""
    user = get_current_user(request)
    
    # For development, create a default user if none exists
    if not user:
        user = {
            'login': 'demo-user',
            'email': 'demo@example.com',
            'name': 'Demo User',
            'orgs': [],
            'github_id': 'demo'
        }
    
    # Allow unauthenticated access for demo purposes
    # In production, you might want to require authentication
    
    # Get filter parameters
    grade_filter = request.query_params.get("grade", "")
    kind_filter = request.query_params.get("kind", "")
    search_query = request.query_params.get("search", "")
    
    # Check for audit_id and status parameters from setup-project redirect
    audit_id = request.query_params.get("audit_id")
    status_param = request.query_params.get("status")
    
    print(f"DEBUG: Dashboard loaded with audit_id={audit_id}, status={status_param}")
    print(f"DEBUG: Session current_audit: {request.session.get('current_audit')}")
    
    # Get user-specific audits using the same logic as api_list_user_audits
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    projects_dir = user_workspace / "projects"
    
    audits = []
    import json
    from datetime import datetime
    
    # Method 1: Check new project structure
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            # Check for metadata files directly in branch directory
                            for metadata_file in branch_dir.glob("*_metadata.json"):
                                try:
                                    with open(metadata_file, 'r') as f:
                                        audit_data = json.load(f)
                                        # Add project info
                                        audit_data['repo_name'] = project_dir.name.replace('~', '/')
                                        audit_data['branch'] = branch_dir.name
                                        audit_data['ts'] = audit_data.get('id', metadata_file.stem.replace('_metadata', ''))
                                        audits.append(audit_data)
                                except Exception as e:
                                    print(f"Error loading audit metadata from {metadata_file}: {e}")
                            
                            # Also check old runs directory structure
                            runs_dir = branch_dir / "runs"
                            if runs_dir.exists():
                                for run_dir in runs_dir.iterdir():
                                    if run_dir.is_dir():
                                        status_file = run_dir / "status.json"
                                        if status_file.exists():
                                            try:
                                                with open(status_file, 'r') as f:
                                                    audit_data = json.load(f)
                                                    # Add project info
                                                    audit_data['repo_name'] = project_dir.name.replace('~', '/')
                                                    audit_data['branch'] = branch_dir.name
                                                    audit_data['ts'] = run_dir.name
                                                    audits.append(audit_data)
                                            except Exception as e:
                                                print(f"Error loading audit metadata from runs: {e}")
    
    # Method 2: Check legacy audits directory for backward compatibility
    legacy_audits_dir = user_workspace / "audits"
    if legacy_audits_dir.exists():
        for audit_dir in legacy_audits_dir.iterdir():
            if audit_dir.is_dir():
                # Check for status and metadata files
                for status_file in audit_dir.glob("*_status.json"):
                    try:
                        if status_file.stat().st_size > 0:  # Skip empty files
                            with open(status_file, 'r') as f:
                                audit_data = json.load(f)
                                # Extract repo name and branch from audit ID if not present
                                if 'repo_name' not in audit_data:
                                    parts = audit_dir.name.split('_')
                                    if len(parts) >= 2:
                                        audit_data['repo_name'] = parts[0]
                                        audit_data['branch'] = parts[1]
                                audit_data['ts'] = audit_dir.name
                                audits.append(audit_data)
                    except Exception as e:
                        print(f"Error loading legacy audit metadata from {status_file}: {e}")
                
                # Also check for metadata files
                for metadata_file in audit_dir.glob("*_metadata.json"):
                    try:
                        with open(metadata_file, 'r') as f:
                            audit_data = json.load(f)
                            # Don't duplicate if we already have this audit
                            audit_id = audit_data.get('id', audit_dir.name)
                            if not any(a.get('id') == audit_id for a in audits):
                                audit_data['ts'] = audit_dir.name
                                audits.append(audit_data)
                    except Exception as e:
                        print(f"Error loading legacy audit metadata from {metadata_file}: {e}")
    
    # Check for in-progress audit from parameters or session
    in_progress_audit = None
    
    # Priority 1: Check for audit_id parameter (from setup-project redirect)
    if audit_id:
        print(f"DEBUG: Found audit_id parameter: {audit_id}")
        # Check if this audit is already in our list
        existing_audit = next((a for a in audits if a.get('id') == audit_id), None)
        if not existing_audit:
            print(f"DEBUG: Audit {audit_id} not found in filesystem, creating in-progress entry")
            # Create a temporary audit entry for in-progress audit
            # Try to get repo info from session
            current_audit = request.session.get('current_audit', {})
            in_progress_audit = {
                'id': audit_id,
                'status': status_param or 'processing',
                'created_at': current_audit.get('created_at', datetime.utcnow().isoformat()),
                'repo_name': current_audit.get('repo_name', 'Loading...'),
                'branch': current_audit.get('branch', 'main'),
                'security_score': None,
                'test_count': None,
                'grade': 'In Progress'
            }
    
    # Priority 2: Check session for current audit if no parameter
    elif not audit_id:
        current_audit = request.session.get('current_audit')
        if current_audit:
            audit_id = current_audit.get('id')
            print(f"DEBUG: Found current_audit in session: {audit_id}")
            # Check if this audit is already in our list
            existing_audit = next((a for a in audits if a.get('id') == audit_id), None)
            if not existing_audit:
                print(f"DEBUG: Session audit {audit_id} not found in filesystem, creating in-progress entry")
                in_progress_audit = {
                    'id': audit_id,
                    'status': current_audit.get('status', 'processing'),
                    'created_at': current_audit.get('created_at', datetime.utcnow().isoformat()),
                    'repo_name': current_audit.get('repo_name', 'Loading...'),
                    'branch': current_audit.get('branch', 'main'),
                    'security_score': None,
                    'test_count': None,
                    'grade': 'In Progress'
                }
    
    # Add in-progress audit to the list
    if in_progress_audit:
        print(f"DEBUG: Adding in-progress audit to list: {in_progress_audit['id']}")
        audits.insert(0, in_progress_audit)  # Insert at beginning to show at top
    
    # Sort by created_at, most recent first
    runs = sorted(audits, key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Apply filters
    filtered_runs = runs
    if grade_filter:
        filtered_runs = [r for r in filtered_runs if r.get('grade', '') == grade_filter]
    if kind_filter:
        filtered_runs = [r for r in filtered_runs if r.get('kind', '') == kind_filter]
    if search_query:
        filtered_runs = [r for r in filtered_runs if search_query.lower() in r.get('repo_name', '').lower() or search_query.lower() in r.get('id', '').lower()]
    
    # Get unique values for filters
    grades = list(set(r.get('grade', 'Unknown') for r in runs))
    kinds = list(set(r.get('kind', 'Smart Contract') for r in runs))
    
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
    """Run detail page with timeline and streaming logs."""
    user = get_current_user(request)
    
    # For development, create a default user if none exists
    if not user:
        user = {
            'login': 'demo-user',
            'email': 'demo@example.com',
            'name': 'Demo User',
            'orgs': [],
            'github_id': 'demo'
        }
    
    # Get audit data for this timestamp
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    projects_dir = user_workspace / "projects"
    
    audit_data = None
    import json
    
    # Search for the audit data in projects structure
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            # Check for metadata files
                            for metadata_file in branch_dir.glob("*_metadata.json"):
                                if ts in metadata_file.name:
                                    try:
                                        with open(metadata_file, 'r') as f:
                                            audit_data = json.load(f)
                                            audit_data['repo_name'] = project_dir.name.replace('~', '/')
                                            audit_data['branch'] = branch_dir.name
                                            break
                                    except Exception as e:
                                        print(f"Error loading audit metadata: {e}")
                        if audit_data:
                            break
                if audit_data:
                    break
    
    # Check legacy audits directory
    if not audit_data:
        legacy_audits_dir = user_workspace / "audits"
        if legacy_audits_dir.exists():
            audit_dir = legacy_audits_dir / ts
            if audit_dir.exists():
                for metadata_file in audit_dir.glob("*_metadata.json"):
                    try:
                        with open(metadata_file, 'r') as f:
                            audit_data = json.load(f)
                            if 'repo_name' not in audit_data:
                                parts = ts.split('_')
                                if len(parts) >= 2:
                                    audit_data['repo_name'] = parts[0]
                                    audit_data['branch'] = parts[1]
                            break
                    except Exception as e:
                        print(f"Error loading legacy audit metadata: {e}")
    
    return templates.TemplateResponse("run_detail.html", {
        "request": request,
        "user": user,
        "audit": audit_data,
        "ts": ts
    })

async def portfolio_page(request: Request):
    """Portfolio overview page - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to landing page if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
    
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

async def projects_page(request: Request):
    """Projects page showing all projects with branches and status."""
    return templates.TemplateResponse("projects.html", {"request": request})

async def download_pdf(request: Request, ts: str):
    """Download PDF for a run - requires authentication."""
    user = get_current_user(request)
    
    # For development, create a default user if none exists
    if not user:
        user = {
            'login': 'demo-user',
            'email': 'demo@example.com',
            'name': 'Demo User',
            'orgs': [],
            'github_id': 'demo'
        }
    
    # Get audit data for this timestamp using new system
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    projects_dir = user_workspace / "projects"
    
    pdf_path = None
    audit_data = None
    import json
    
    # Search for the audit data and PDF
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            # Check for metadata files
                            for metadata_file in branch_dir.glob("*_metadata.json"):
                                if ts in metadata_file.name:
                                    try:
                                        with open(metadata_file, 'r') as f:
                                            audit_data = json.load(f)
                                            # Look for PDF in result path
                                            if audit_data.get('result_path'):
                                                result_path = Path(audit_data['result_path'])
                                                pdf_file = result_path / "report.pdf"
                                                if pdf_file.exists():
                                                    pdf_path = pdf_file
                                                    break
                                    except Exception as e:
                                        print(f"Error loading audit metadata: {e}")
                        if pdf_path:
                            break
                if pdf_path:
                    break
    
    if not pdf_path or not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # Use repo name for filename if available
    repo_name = audit_data.get('repo_name', 'audit') if audit_data else 'audit'
    branch_name = audit_data.get('branch_name', 'main') if audit_data else 'main'
    
    return FileResponse(
        pdf_path,
        media_type='application/pdf',
        filename=f"{repo_name}-{branch_name}-audit.pdf"
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

async def onboarding_repos(request: Request):
    """Onboarding step 2: Repository selection page."""
    user = get_current_user(request)
    
    # For development, create a default user if none exists
    if not user:
        user = {
            'login': 'demo-user',
            'email': 'demo@example.com',
            'name': 'Demo User',
            'orgs': [],
            'github_id': 'demo'
        }
    
    return templates.TemplateResponse("onboarding_repos.html", {
        "request": request,
        "user": user
    })

async def api_github_repos(request: Request):
    """API endpoint to fetch user's GitHub repositories."""
    print(f"=== REAL api_github_repos from views.py called ===")
    import httpx
    from fastapi import HTTPException
    
    user = get_current_user(request)
    
    # For development, create a temporary user if no GitHub auth
    if not user:
        print("No user found in repos API, creating dev user")
        user = {
            'login': 'dev-user',
            'email': 'dev@example.com', 
            'name': 'Development User'
        }
        # Store user in session for consistency
        from .security import set_user_session
        set_user_session(request, user)
    
    # Get GitHub token from session
    github_token = request.session.get('github_token') or user.get('github_token')
    
    print(f"DEBUG: User found: {bool(user)}")
    print(f"DEBUG: User login: {user.get('login') if user else 'None'}")
    print(f"DEBUG: Session github_token: {bool(request.session.get('github_token'))}")
    print(f"DEBUG: User github_token: {bool(user.get('github_token') if user else False)}")
    print(f"DEBUG: Final github_token: {bool(github_token)}")
    
    if not github_token:
        print("DEBUG: No GitHub token found, returning mock repositories")
        # Return mock repositories for demo
        return await get_mock_repositories(user)
    
    print(f"DEBUG: Making GitHub API call with token: {github_token[:10]}...")
    try:
        async with httpx.AsyncClient() as client:
            # Fetch user repositories
            repos_response = await client.get(
                'https://api.github.com/user/repos',
                headers={
                    'Authorization': f'token {github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                },
                params={
                    'sort': 'updated',
                    'per_page': 50,
                    'type': 'all'
                }
            )
            
            print(f"DEBUG: GitHub API response status: {repos_response.status_code}")
            if repos_response.status_code != 200:
                print(f"GitHub API error: {repos_response.status_code} - {repos_response.text}")
                print(f"DEBUG: Falling back to mock repositories due to API error")
                return await get_mock_repositories(user)
            
            repos_data = repos_response.json()
            print(f"DEBUG: Successfully fetched {len(repos_data)} repositories from GitHub API")
            
            # Format repositories for frontend
            formatted_repos = []
            for repo in repos_data:
                formatted_repos.append({
                    'id': repo['id'],
                    'name': repo['name'],
                    'full_name': repo['full_name'],
                    'description': repo['description'] or 'No description provided',
                    'stargazers_count': repo['stargazers_count'],
                    'forks_count': repo['forks_count'],
                    'language': repo['language'],
                    'updated_at': repo['updated_at'],
                    'created_at': repo['created_at'],
                    'size': repo['size'],
                    'open_issues_count': repo['open_issues_count'],
                    'default_branch': repo['default_branch'],
                    'private': repo['private'],
                    'html_url': repo['html_url'],
                    'clone_url': repo['clone_url']
                })
            
            print(f"DEBUG: Returning {len(formatted_repos)} formatted repositories")
            return formatted_repos
            
    except Exception as e:
        print(f"Error fetching GitHub repositories: {e}")
        print(f"DEBUG: Exception occurred, falling back to mock repositories")
        # Fallback to mock data on error
        return await get_mock_repositories(user)

async def get_mock_repositories(user: dict):
    """Return mock repositories for testing."""
    mock_repos = [
        {
            "id": 1,
            "name": "sample-contract",
            "full_name": f"{user.get('login', 'user')}/sample-contract",
            "description": "A sample smart contract for demonstration purposes with basic functionality",
            "stargazers_count": 5,
            "forks_count": 2,
            "language": "Solidity",
            "updated_at": "2024-01-15T10:30:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "size": 1024,
            "open_issues_count": 1,
            "default_branch": "main"
        },
        {
            "id": 2,
            "name": "defi-protocol",
            "full_name": f"{user.get('login', 'user')}/defi-protocol",
            "description": "DeFi protocol implementation with advanced features including yield farming and liquidity pools",
            "stargazers_count": 12,
            "forks_count": 3,
            "language": "Solidity",
            "updated_at": "2024-01-20T14:45:00Z",
            "created_at": "2024-01-10T00:00:00Z",
            "size": 2048,
            "open_issues_count": 3,
            "default_branch": "main"
        },
        {
            "id": 3,
            "name": "nft-marketplace",
            "full_name": f"{user.get('login', 'user')}/nft-marketplace",
            "description": "NFT marketplace smart contracts with minting, trading, and auction functionality",
            "stargazers_count": 8,
            "forks_count": 1,
            "language": "Solidity",
            "updated_at": "2024-01-18T09:15:00Z",
            "created_at": "2024-01-05T00:00:00Z",
            "size": 1536,
            "open_issues_count": 2,
            "default_branch": "main"
        },
        {
            "id": 4,
            "name": "governance-token",
            "full_name": f"{user.get('login', 'user')}/governance-token",
            "description": "DAO governance token with voting mechanisms and proposal management",
            "stargazers_count": 15,
            "forks_count": 5,
            "language": "Solidity",
            "updated_at": "2024-01-22T16:45:00Z",
            "created_at": "2024-01-12T00:00:00Z",
            "size": 1280,
            "open_issues_count": 4,
            "default_branch": "main"
        },
        {
            "id": 5,
            "name": "lending-protocol",
            "full_name": f"{user.get('login', 'user')}/lending-protocol",
            "description": "Decentralized lending protocol with collateral management and interest calculation",
            "stargazers_count": 20,
            "forks_count": 7,
            "language": "Solidity",
            "updated_at": "2024-01-25T11:20:00Z",
            "created_at": "2024-01-15T00:00:00Z",
            "size": 2560,
            "open_issues_count": 6,
            "default_branch": "main"
        },
        {
            "id": 6,
            "name": "oracle-service",
            "full_name": f"{user.get('login', 'user')}/oracle-service",
            "description": "Blockchain oracle service for off-chain data integration",
            "stargazers_count": 6,
            "forks_count": 2,
            "language": "Solidity",
            "updated_at": "2024-01-16T13:10:00Z",
            "created_at": "2024-01-08T00:00:00Z",
            "size": 896,
            "open_issues_count": 1,
            "default_branch": "main"
        }
    ]
    
    return mock_repos

async def api_github_branches(request: Request):
    """API endpoint to fetch branches for a specific repository."""
    print(f"=== REAL api_github_branches from views.py called ===")
    import httpx
    from fastapi import HTTPException
    
    user = get_current_user(request)
    
    if not user:
        print("No user found, creating dev user for branches API")
        # For development, create a temporary user and set session
        user = {
            'login': 'dev-user',
            'email': 'dev@example.com', 
            'name': 'Development User'
        }
        # Store user in session for consistency
        from .security import set_user_session
        set_user_session(request, user)
    
    # Get repository from query params
    repo_name = request.query_params.get('repo')
    if not repo_name:
        raise HTTPException(status_code=400, detail="Repository name required")
    
    # Get GitHub token from session
    github_token = request.session.get('github_token') or user.get('github_token')
    
    print(f"Fetching branches for: {repo_name}, token present: {bool(github_token)}")
    
    # Determine repository owner/name for API call
    repo_owner = None
    repo_full_name = None
    
    # Try to get the correct owner from known mappings or GitHub API
    if repo_name == "TribesByAstrix":
        repo_owner = "astrix-tribes"
        repo_full_name = f"{repo_owner}/{repo_name}"
    else:
        # Try to get from user's repositories if we have a token
        if github_token:
            try:
                async with httpx.AsyncClient() as client:
                    # First try to get from user's repos
                    repos_response = await client.get(
                        'https://api.github.com/user/repos',
                        headers={
                            'Authorization': f'token {github_token}',
                            'Accept': 'application/vnd.github.v3+json'
                        },
                        params={'per_page': 100}
                    )
                    if repos_response.status_code == 200:
                        repos = repos_response.json()
                        for repo in repos:
                            if repo.get('name') == repo_name:
                                repo_owner = repo.get('owner', {}).get('login')
                                repo_full_name = repo.get('full_name')
                                break
            except Exception as e:
                print(f"Error fetching user repos to find owner: {e}")
        
        # Fallback to user login if not found
        if not repo_full_name:
            repo_owner = user.get('login', 'dev-user')
            repo_full_name = f"{repo_owner}/{repo_name}"
    
    print(f"Using repo full name: {repo_full_name}")
    
    if not github_token:
        # Return realistic branches for TribesByAstrix based on what we know
        if repo_name == "TribesByAstrix":
            return [
                {
                    'name': 'main',
                    'commit': {
                        'sha': '19f2ead89d6a639bc8357d90739ddb0600e2e82c',
                        'url': f'https://api.github.com/repos/{repo_full_name}/commits/19f2ead89d6a639bc8357d90739ddb0600e2e82c'
                    },
                    'protected': True
                },
                {
                    'name': 'testing',
                    'commit': {
                        'sha': 'aa9ad7daa9233cc2c39be521efb7083195ff6b8d',
                        'url': f'https://api.github.com/repos/{repo_full_name}/commits/aa9ad7daa9233cc2c39be521efb7083195ff6b8d'
                    },
                    'protected': False
                },
                {
                    'name': 'readme-contracts',
                    'commit': {
                        'sha': 'e0199b529c12ae42264cf2fd383cbbc1fe58f717',
                        'url': f'https://api.github.com/repos/{repo_full_name}/commits/e0199b529c12ae42264cf2fd383cbbc1fe58f717'
                    },
                    'protected': False
                }
            ]
        else:
            # Generic branches for other repos
            return [
                {
                    'name': 'main',
                    'commit': {
                        'sha': 'abc123',
                        'url': f'https://api.github.com/repos/{repo_full_name}/commits/abc123'
                    },
                    'protected': True
                },
                {
                    'name': 'develop',
                    'commit': {
                        'sha': 'def456',
                        'url': f'https://api.github.com/repos/{repo_full_name}/commits/def456'
                    },
                    'protected': False
                }
            ]
    
    try:
        async with httpx.AsyncClient() as client:
            # Fetch repository branches using full repo name
            branches_response = await client.get(
                f'https://api.github.com/repos/{repo_full_name}/branches',
                headers={
                    'Authorization': f'token {github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
            )
            
            print(f"GitHub API response status: {branches_response.status_code}")
            
            if branches_response.status_code != 200:
                print(f"GitHub API error for branches: {branches_response.status_code} - {branches_response.text}")
                # Fallback to public API without token
                if branches_response.status_code == 404 or branches_response.status_code == 403:
                    print("Trying public API without token...")
                    public_response = await client.get(
                        f'https://api.github.com/repos/{repo_full_name}/branches'
                    )
                    if public_response.status_code == 200:
                        branches_response = public_response
                    else:
                        raise HTTPException(status_code=public_response.status_code, detail="Failed to fetch branches")
                else:
                    raise HTTPException(status_code=branches_response.status_code, detail="Failed to fetch branches")
            
            branches_data = branches_response.json()
            
            # Format branches for frontend
            formatted_branches = []
            for branch in branches_data:
                formatted_branches.append({
                    'name': branch['name'],
                    'commit': {
                        'sha': branch['commit']['sha'],
                        'url': branch['commit']['url']
                    },
                    'protected': branch.get('protected', False)
                })
            
            print(f"Successfully fetched {len(formatted_branches)} branches")
            return formatted_branches
            
    except Exception as e:
        print(f"Error fetching GitHub branches: {e}")
        # Return fallback branches on error
        return [
            {
                'name': 'main',
                'commit': {
                    'sha': 'main-commit',
                    'url': f'https://api.github.com/repos/{repo_full_name}/commits/main-commit'
                },
                'protected': True
            }
        ]

def get_user_workspace(user_login: str) -> Path:
    """Get or create user-specific workspace directory."""
    # Use a writable directory - try multiple options
    possible_roots = [
        Path.home() / ".uatu_audit" / "workspaces",  # User home directory
        Path("/tmp") / "uatu_audit" / "workspaces",   # System temp directory
        Path.cwd() / "tmp" / "workspaces",            # Project temp directory
    ]
    
    workspace_root = None
    for root in possible_roots:
        try:
            test_path = root / "test_write"
            test_path.mkdir(parents=True, exist_ok=True)
            test_file = test_path / "test.txt"
            test_file.write_text("test")
            test_file.unlink()
            test_path.rmdir()
            workspace_root = root
            print(f"Using workspace root: {workspace_root}")
            break
        except (PermissionError, OSError) as e:
            print(f"Cannot use {root}: {e}")
            continue
    
    if not workspace_root:
        raise RuntimeError("No writable directory found for user workspaces")
    
    # Ensure strict permissions on workspace root and user directory
    try:
        workspace_root.mkdir(parents=True, exist_ok=True)
        os.chmod(workspace_root, 0o700)
    except Exception:
        pass

    user_workspace = workspace_root / user_login
    user_workspace.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(user_workspace, 0o700)
    except Exception:
        pass

    # Pre-create segregated subdirs with restrictive permissions
    for sub in ("repos", "audits"):
        sd = user_workspace / sub
        sd.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(sd, 0o700)
        except Exception:
            pass
    return user_workspace

def generate_audit_id(repo_name: str, branch: str, user: str) -> str:
    """Generate unique audit ID based on repo, branch, and timestamp."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    content = f"{user}_{repo_name}_{branch}_{timestamp}"
    short_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{repo_name}_{branch}_{timestamp}_{short_hash}"

async def clone_repository(repo_url: str, branch: str, clone_path: Path, github_token: str = None) -> bool:
    """Clone repository with optional GitHub token for private repos."""
    try:
        # Prepare clone command
        if github_token:
            # Use token for private repos
            repo_url_with_token = repo_url.replace('https://github.com/', f'https://{github_token}@github.com/')
            cmd = ["git", "clone", "-b", branch, "--depth", "1", repo_url_with_token, str(clone_path)]
        else:
            # Public repo
            cmd = ["git", "clone", "-b", branch, "--depth", "1", repo_url, str(clone_path)]
        
        # Run clone command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"Successfully cloned {repo_url}@{branch}")
            return True
        else:
            print(f"Clone failed: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"Error cloning repository: {e}")
        return False

async def run_audit_process(audit_path: Path, audit_id: str, user_login: str, repo_name: str | None = None, branch_name: str | None = None, repo_owner: str | None = None) -> dict:
    """Run the UatuAudit process on cloned repository with test generation."""
    try:
        # Import the Orchestrator from core and centralized logging
        from ..core import Orchestrator
        from .centralized_logging import get_centralized_logger, AuditPhase, LogLevel
        
        # Determine repo/branch for project layout
        repo_name = repo_name or audit_path.name
        branch_name = branch_name or 'main'
        repo_owner = repo_owner or user_login

        user_workspace = get_user_workspace(user_login)
        project_id = (repo_name or 'adhoc').replace('/', '~')
        project_root = user_workspace / 'projects' / project_id
        branch_root = project_root / 'branches' / (branch_name or 'main')
        (branch_root / 'shared').mkdir(parents=True, exist_ok=True)
        
        # Create/update project metadata file for proper name display
        project_metadata = {
            "project_id": project_id,
            "repo_name": repo_name,
            "repo_owner": repo_owner,
            "created_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
        }
        project_metadata_file = project_root / 'project.json'
        project_metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(project_metadata_file, 'w') as f:
            import json
            json.dump(project_metadata, f, indent=2)

        # Orchestrator out_root will be branch_root; it will create runs/<ts>
        audit_output = branch_root
        
        # Initialize centralized logging
        logger = get_centralized_logger(project_root, branch_name, audit_id)
        logger.log(LogLevel.INFO, AuditPhase.INIT, f"Starting audit for {repo_name}@{branch_name}")
        logger.update_phase(AuditPhase.ANALYSIS, 10, "running", "Starting analysis phase")
        
        # Create orchestrator instance
        orchestrator = Orchestrator(
            input_path_or_address=str(audit_path),
            kind="evm",  # Default to EVM, could be configurable
            out_root=audit_output,
            llm=True,  # Enable LLM for better results
            risk=True,  # Enable risk scoring
            badge=True,  # Generate badges
            trend=True,  # Generate trends
            pdf=True,  # Generate PDF reports
        )
        
        # Update to test generation phase
        logger.update_phase(AuditPhase.TEST_GEN, 40, "running", "Generating test cases")
        
        # Run the audit process (this includes test generation)
        result_path = orchestrator.run()
        
        # Mark as completed
        logger.complete(f"Audit completed successfully, results at: {result_path}")
        
        # Create audit result metadata with actual repo name
        audit_result = {
            "id": audit_id,
            "user": user_login,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "result_path": str(result_path),
            "repo_path": str(audit_path),
            "repo_name": repo_name,  # Store actual repo name for display
            "branch_name": branch_name,
            "has_tests": True,  # Tests are generated by orchestrator
        }
        
        # Save metadata
        metadata_file = audit_output / f"{audit_id}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(audit_result, f, indent=2)

        # Back-compat: mirror status/metadata to legacy folder for existing UI
        legacy_dir = user_workspace / 'audits' / audit_id
        legacy_dir.mkdir(parents=True, exist_ok=True)
        with open(legacy_dir / f"{audit_id}_status.json", 'w') as f:
            json.dump(audit_result, f, indent=2)
        with open(legacy_dir / f"{audit_id}_metadata.json", 'w') as f:
            json.dump(audit_result, f, indent=2)
        
        print(f"Audit completed for {audit_id}: {result_path}")
        return audit_result
        
    except Exception as e:
        print(f"Audit process failed for {audit_id}: {e}")
        # Log error using centralized logging
        try:
            logger.error(AuditPhase.FAILED, f"Audit failed: {str(e)}", e)
        except:
            pass
            
        return {
            "id": audit_id,
            "user": user_login,
            "status": "failed",
            "error": str(e),
            "created_at": datetime.utcnow().isoformat(),
        }

async def setup_project(request: Request):
    """Setup project with selected repository and start audit process."""
    try:
        # Debug session contents
        print(f"Session contents: {dict(request.session)}")
        
        user = get_current_user(request)
        print(f"Current user: {user}")
        
        if not user:
            print("No user found in session - checking for development mode")
            # For development, always allow setup-project to proceed
            print("Development mode: Creating temporary user for testing")
            user = {
                'login': 'dev-user',
                'email': 'dev@example.com', 
                'name': 'Development User'
            }
            # Store user in session for consistency
            from .security import set_user_session
            set_user_session(request, user)
        
        # Get repository and branch from query params
        repo_name = request.query_params.get("repo")
        branch_name = request.query_params.get("branch", "main")
        
        if not repo_name:
            raise HTTPException(status_code=400, detail="Repository name required")
        
        # Generate unique audit ID
        user_login = user.get('login', 'demo-user')
        audit_id = generate_audit_id(repo_name, branch_name, user_login)
        
        # Get user workspace
        user_workspace = get_user_workspace(user_login)
        
        # Setup paths
        repo_clone_path = user_workspace / "repos" / audit_id
        repo_clone_path.mkdir(parents=True, exist_ok=True)
        
        # Get GitHub token for private repos
        github_token = request.session.get('github_token')
        
        # Get repository details from GitHub API to get the correct owner/URL
        repo_url = None
        repo_owner = None
        
        try:
            import httpx
            if github_token:
                async with httpx.AsyncClient() as client:
                    repos_response = await client.get(
                        'https://api.github.com/user/repos',
                        headers={
                            'Authorization': f'token {github_token}',
                            'Accept': 'application/vnd.github.v3+json'
                        },
                        params={'per_page': 100}
                    )
                    if repos_response.status_code == 200:
                        repos = repos_response.json()
                        for repo in repos:
                            if repo.get('name') == repo_name:
                                repo_url = repo.get('clone_url', repo.get('git_url', ''))
                                repo_owner = repo.get('owner', {}).get('login', user_login)
                                break
        except Exception as e:
            print(f"Error fetching repo details from GitHub API: {e}")
        
        # Fallback to constructing URL if API call failed
        if not repo_url:
            # For development, try common patterns or use GitHub search
            if repo_name == "TribesByAstrix":
                repo_owner = "astrix-tribes"
            else:
                repo_owner = user_login
            repo_url = f"https://github.com/{repo_owner}/{repo_name}.git"
        
        # Debug logging
        print(f"Debug setup_project:")
        print(f"  User: {user_login}")
        print(f"  Repo: {repo_name}")
        print(f"  Branch: {branch_name}")
        print(f"  GitHub token present: {bool(github_token)}")
        print(f"  Repo URL: {repo_url}")
        print(f"  Repo owner: {repo_owner}")
        print(f"  Audit ID: {audit_id}")
        print(f"  Clone path: {repo_clone_path}")
        
        # Store audit session info
        request.session['current_audit'] = {
            'id': audit_id,
            'repo_name': repo_name,
            'branch': branch_name,
            'user': user_login,
            'status': 'cloning',
            'created_at': datetime.utcnow().isoformat()
        }
        

        # Start background task using asyncio
        async def _runner():
            try:
                # Clone repository first
                clone_success = await clone_repository(repo_url, branch_name, repo_clone_path, github_token)
                
                if clone_success:
                    print(f"Clone successful for {audit_id}, starting audit process")
                    # Run audit process
                    await run_audit_process(repo_clone_path, audit_id, user_login, repo_name=repo_name, branch_name=branch_name, repo_owner=repo_owner)
                    print(f"Audit workflow completed for {audit_id}")
                else:
                    print(f"Clone failed for {audit_id}")
                    # Handle clone failure - could store error state
                    
            except Exception as e:
                print(f"Audit workflow failed for {audit_id}: {e}")
        
        # Create and store the task to prevent garbage collection
        task = asyncio.create_task(_runner())
        # Store task reference to prevent garbage collection
        if not hasattr(setup_project, '_background_tasks'):
            setup_project._background_tasks = set()
        setup_project._background_tasks.add(task)
        task.add_done_callback(setup_project._background_tasks.discard)
        
        print(f"Queued audit for {user_login}: {repo_name}@{branch_name} (ID: {audit_id})")
        
        # Redirect to dashboard with audit info
        return RedirectResponse(url=f"/dashboard?audit_id={audit_id}&status=processing")
    
    except Exception as e:
        print(f"Error in setup_project: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Setup failed: {str(e)}")

async def api_audit_status(request: Request):
    """Get audit status for current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    audit_id = request.query_params.get("audit_id")
    if not audit_id:
        # Return current audit from session
        current_audit = request.session.get('current_audit')
        if current_audit:
            return current_audit
        else:
            raise HTTPException(status_code=404, detail="No audit found")
    
    # Check if audit exists in user workspace
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    audit_metadata_path = user_workspace / "audits" / audit_id / f"{audit_id}_metadata.json"
    
    if audit_metadata_path.exists():
        import json
        try:
            with open(audit_metadata_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading audit metadata: {e}")
            # Fallback to session
            current_audit = request.session.get('current_audit', {})
            if current_audit.get('id') == audit_id:
                return current_audit
            else:
                return {"id": audit_id, "status": "unknown", "error": str(e)}
    else:
        # Return session info as fallback
        current_audit = request.session.get('current_audit', {})
        if current_audit.get('id') == audit_id:
            return current_audit
        else:
            raise HTTPException(status_code=404, detail="Audit not found")

async def api_quick_status(request: Request):
    """Quick status endpoint that returns immediately without heavy I/O."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_login = user.get('login', 'demo-user')
    
    # Get current audit from session (fastest)
    current_audit = request.session.get('current_audit')
    
    # Check if we have any projects at all (quick directory check)
    try:
        ws = get_user_workspace(user_login)
        projects_root = ws / 'projects'
        has_projects = projects_root.exists() and any(projects_root.iterdir())
    except Exception:
        has_projects = False
    
    return {
        "user": user_login,
        "current_audit": current_audit,
        "has_projects": has_projects,
        "timestamp": datetime.utcnow().isoformat()
    }

async def api_list_user_audits(request: Request):
    """List all audits for current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    projects_dir = user_workspace / "projects"
    
    audits = []
    import json
    from datetime import datetime
    
    # Method 1: Check new project structure
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                branches_dir = project_dir / "branches"
                if branches_dir.exists():
                    for branch_dir in branches_dir.iterdir():
                        if branch_dir.is_dir():
                            # Check for metadata files directly in branch directory
                            for metadata_file in branch_dir.glob("*_metadata.json"):
                                try:
                                    with open(metadata_file, 'r') as f:
                                        audit_data = json.load(f)
                                        # Add project info
                                        audit_data['repo_name'] = project_dir.name.replace('~', '/')
                                        audit_data['branch'] = branch_dir.name
                                        audit_data['ts'] = audit_data.get('id', metadata_file.stem.replace('_metadata', ''))
                                        audits.append(audit_data)
                                except Exception as e:
                                    print(f"Error loading audit metadata from {metadata_file}: {e}")
                            
                            # Also check old runs directory structure
                            runs_dir = branch_dir / "runs"
                            if runs_dir.exists():
                                for run_dir in runs_dir.iterdir():
                                    if run_dir.is_dir():
                                        status_file = run_dir / "status.json"
                                        if status_file.exists():
                                            try:
                                                with open(status_file, 'r') as f:
                                                    audit_data = json.load(f)
                                                    # Add project info
                                                    audit_data['repo_name'] = project_dir.name.replace('~', '/')
                                                    audit_data['branch'] = branch_dir.name
                                                    audit_data['ts'] = run_dir.name
                                                    audits.append(audit_data)
                                            except Exception as e:
                                                print(f"Error loading audit metadata from runs: {e}")
    
    # Method 2: Check legacy audits directory for backward compatibility
    legacy_audits_dir = user_workspace / "audits"
    if legacy_audits_dir.exists():
        for audit_dir in legacy_audits_dir.iterdir():
            if audit_dir.is_dir():
                # Check for status and metadata files
                for status_file in audit_dir.glob("*_status.json"):
                    try:
                        if status_file.stat().st_size > 0:  # Skip empty files
                            with open(status_file, 'r') as f:
                                audit_data = json.load(f)
                                # Extract repo name and branch from audit ID if not present
                                if 'repo_name' not in audit_data:
                                    parts = audit_dir.name.split('_')
                                    if len(parts) >= 2:
                                        audit_data['repo_name'] = parts[0]
                                        audit_data['branch'] = parts[1]
                                audit_data['ts'] = audit_dir.name
                                audits.append(audit_data)
                    except Exception as e:
                        print(f"Error loading legacy audit metadata from {status_file}: {e}")
                
                # Also check for metadata files
                for metadata_file in audit_dir.glob("*_metadata.json"):
                    try:
                        with open(metadata_file, 'r') as f:
                            audit_data = json.load(f)
                            # Don't duplicate if we already have this audit
                            audit_id = audit_data.get('id', audit_dir.name)
                            if not any(a.get('id') == audit_id for a in audits):
                                audit_data['ts'] = audit_dir.name
                                audits.append(audit_data)
                    except Exception as e:
                        print(f"Error loading legacy audit metadata from {metadata_file}: {e}")
    
    return {"audits": sorted(audits, key=lambda x: x.get('created_at', ''), reverse=True)}

async def test_endpoint(request: Request):
    """Test endpoint for debugging."""
    print("=== test_endpoint called ===")
    return {"message": "Test endpoint working", "path": str(request.url)}

async def test_oauth(request: Request):
    """Test OAuth endpoint for development."""
    from .security import set_user_session
    
    # Create a test user session for Soneshwar (has actual audit data)
    set_user_session(request, {
        'login': 'Soneshwar',
        'email': 'soneshwar@example.com',
        'name': 'Soneshwar',
        'orgs': ['test-org'],
        'github_id': 'soneshwar'
    })
    
    return RedirectResponse(url='/dashboard')

async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

async def debug_workspace(request: Request):
    """Debug workspace structure for troubleshooting."""
    user = get_current_user(request)
    if not user:
        # Allow debug endpoint without auth for testing
        user = {'login': 'demo-user'}
    
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    projects_root = user_workspace / 'projects'
    
    result = {
        "user": user.get('login', 'demo-user'),
        "workspace_root": str(user_workspace),
        "projects_root": str(projects_root),
        "projects_exists": projects_root.exists(),
        "projects": []
    }
    
    if projects_root.exists():
        for proj in projects_root.iterdir():
            if proj.is_dir():
                project_info = {
                    "name": proj.name,
                    "path": str(proj),
                    "has_project_json": (proj / 'project.json').exists(),
                    "branches": []
                }
                
                branches_root = proj / 'branches'
                if branches_root.exists():
                    for branch in branches_root.iterdir():
                        if branch.is_dir():
                            branch_info = {
                                "name": branch.name,
                                "has_logs": (branch / 'logs').exists(),
                                "has_runs": (branch / 'runs').exists()
                            }
                            if branch_info["has_logs"]:
                                logs_dir = branch / 'logs'
                                branch_info["log_files"] = [f.name for f in logs_dir.iterdir()]
                            project_info["branches"].append(branch_info)
                
                result["projects"].append(project_info)
    
    return result

# --- New: Projects and runs listing (provisional grouping) ---
async def api_projects(request: Request):
    """List projects for current user. Optimized for non-blocking operation."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Check if this is a quick status check
    quick = request.query_params.get("quick", "false").lower() == "true"
    
    # Scan user workspace projects with minimal I/O
    ws = get_user_workspace(user.get('login','demo-user'))
    projects_root = ws / 'projects'
    projects = []
    
    if projects_root.exists():
        try:
            # Use asyncio for file operations to avoid blocking
            import asyncio
            import aiofiles
            import aiofiles.os
            
            project_dirs = []
            async for proj in aiofiles.os.scandir(projects_root):
                if proj.is_dir():
                    project_dirs.append(proj)
            
            for proj in sorted(project_dirs, key=lambda x: x.name):
                owner_repo = proj.name.replace('~','/')
                branches_root = Path(proj.path) / 'branches'
                branches = []
                
                if branches_root.exists():
                    branch_dirs = []
                    async for br in aiofiles.os.scandir(branches_root):
                        if br.is_dir():
                            branch_dirs.append(br)
                    
                    for br in sorted(branch_dirs, key=lambda x: x.name):
                        runs_root = Path(br.path) / 'runs'
                        last_run = None
                        
                        if runs_root.exists() and not quick:
                            # For quick requests, skip expensive operations
                            try:
                                # Get most recent run directory without full scan
                                run_dirs = []
                                async for rd in aiofiles.os.scandir(runs_root):
                                    if rd.is_dir():
                                        run_dirs.append(rd.name)
                                
                                if run_dirs:
                                    run_dirs.sort(reverse=True)
                                    latest_run = runs_root / run_dirs[0]
                                    
                                    # Lightweight status check
                                    score = 0.0
                                    grade = 'Info'
                                    status = 'running'
                                    
                                    # Quick existence checks
                                    if (latest_run / 'report.html').exists():
                                        status = 'completed'
                                        # Only read risk.json if report exists (completed)
                                        risk_file = latest_run / 'runs' / 'risk' / 'risk.json'
                                        if risk_file.exists():
                                            try:
                                                async with aiofiles.open(risk_file, 'r') as f:
                                                    content = await f.read()
                                                j = __import__('json').loads(content)
                                                sc = j.get('summary',{})
                                                score = float(sc.get('overall',0.0))
                                                grade = sc.get('grade','Info')
                                            except Exception:
                                                pass
                                    
                                    last_run = {
                                        "ts": run_dirs[0], 
                                        "status": status, 
                                        "score": score, 
                                        "grade": grade, 
                                        "delta": 0.0
                                    }
                            except Exception as e:
                                print(f"Error reading runs for {br.name}: {e}")
                        
                        branches.append({
                            "name": br.name,
                            "last_run": last_run,
                            "errors": 0,
                            "updated_at": datetime.utcnow().isoformat()+"Z"
                        })
                
                # Try to extract real project name from project metadata
                real_project_name = owner_repo
                try:
                    # Check project.json for actual repo name
                    project_metadata_file = proj / 'project.json'
                    if project_metadata_file.exists():
                        import json
                        project_metadata = json.loads(project_metadata_file.read_text())
                        real_project_name = project_metadata.get('repo_name', owner_repo)
                except Exception:
                    pass  # Fall back to directory name
                
                projects.append({
                    "id": real_project_name,
                    "owner_repo": real_project_name,
                    "branches": branches,
                    "settings": {"llm":"auto","journey_cap":5,"stress":"small"}
                })
        except ImportError:
            # Fallback to synchronous if aiofiles not available
            print("aiofiles not available, using synchronous fallback")
            for proj in sorted(projects_root.iterdir()):
                if not proj.is_dir():
                    continue
                owner_repo = proj.name.replace('~','/')
                branches_root = proj / 'branches'
                branches = []
                if branches_root.exists():
                    for br in sorted(branches_root.iterdir()):
                        if not br.is_dir():
                            continue
                        branches.append({
                            "name": br.name,
                            "last_run": None if quick else get_last_run_quick(br / 'runs'),
                            "errors": 0,
                            "updated_at": datetime.utcnow().isoformat()+"Z"
                        })
                
                # Try to extract real project name from project metadata
                real_project_name = owner_repo
                try:
                    # Check project.json for actual repo name
                    project_metadata_file = proj / 'project.json'
                    if project_metadata_file.exists():
                        import json
                        project_metadata = json.loads(project_metadata_file.read_text())
                        real_project_name = project_metadata.get('repo_name', owner_repo)
                except Exception:
                    pass  # Fall back to directory name
                
                projects.append({
                    "id": real_project_name,
                    "owner_repo": real_project_name,
                    "branches": branches,
                    "settings": {"llm":"auto","journey_cap":5,"stress":"small"}
                })
        except Exception as e:
            print(f"Error in api_projects: {e}")
            # Return minimal response on error
            return {"projects": [], "error": "Unable to load projects"}
    
    return {"projects": projects}

def get_last_run_quick(runs_root):
    """Quick synchronous method to get last run info without blocking."""
    if not runs_root.exists():
        return None
    try:
        rdirs = [d.name for d in runs_root.iterdir() if d.is_dir()]
        if not rdirs:
            return None
        rdirs.sort(reverse=True)
        latest = runs_root / rdirs[0]
        status = 'completed' if (latest / 'report.html').exists() else 'running'
        return {
            "ts": rdirs[0],
            "status": status,
            "score": 0.0,
            "grade": 'Info',
            "delta": 0.0
        }
    except Exception:
        return None

async def api_project_runs(request: Request, owner_repo: str):
    """List runs for a given project (placeholder: returns all runs)."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    branch = request.query_params.get('branch','main')
    limit = int(request.query_params.get('limit','50'))
    cursor = request.query_params.get('cursor')
    # Read from project layout directly
    ws = get_user_workspace(user.get('login','demo-user'))
    proj_dir = ws / 'projects' / owner_repo.replace('/','~') / 'branches' / branch
    runs_root = proj_dir / 'runs'
    out = []
    next_cursor = None
    if runs_root.exists():
        rdirs = [d for d in runs_root.iterdir() if d.is_dir()]
        rdirs.sort(reverse=True)
        if cursor:
            rdirs = [d for d in rdirs if d.name < cursor]
        page = rdirs[:limit]
        if len(page) == limit:
            next_cursor = page[-1].name
        for rd in page:
            score = 0.0
            grade = 'Info'
            risk = rd / 'runs' / 'risk' / 'risk.json'
            if risk.exists():
                try:
                    j = __import__('json').loads(risk.read_text())
                    sc = j.get('summary',{})
                    score = float(sc.get('overall',0.0))
                    grade = sc.get('grade','Info')
                except Exception:
                    pass
            out.append({
                "ts": rd.name,
                "status": 'completed' if (rd / 'report.html').exists() else 'running',
                "phase": 'report' if (rd / 'report.html').exists() else 'analysis',
                "pct": 100 if (rd / 'report.html').exists() else 0,
                "score": score,
                "grade": grade,
                "delta": 0.0,
                "artifact": {"html": str(rd / 'report.html'), "pdf": str(rd / 'report.pdf') if (rd / 'report.pdf').exists() else None}
            })
    return {"branch": branch, "runs": out, "next": next_cursor}

# --- New: Run status and logs APIs ---
async def api_run_status(request: Request, ts: str):
    """Return status for a given run timestamp using centralized logging."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Try centralized status first
    from .centralized_logging import get_run_status
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    
    # Find project and branch for this run
    projects_root = user_workspace / 'projects'
    if projects_root.exists():
        for proj in projects_root.iterdir():
            if not proj.is_dir():
                continue
            for branch_dir in (proj / 'branches').iterdir() if (proj / 'branches').exists() else []:
                if not branch_dir.is_dir():
                    continue
                # Check if this run exists in this branch
                status = get_run_status(proj, branch_dir.name, ts)
                if status:
                    return status
    
    # Fallback to old system
    run = indexer.get_run_by_ts(ts)
    if not run:
        # Return a default pending status for missing runs
        return {
            "ts": ts, 
            "run_id": ts,
            "phase": "unknown", 
            "status": "not_found",
            "progress_pct": 0,
            "created_at": "2025-09-04T18:03:21.383464",
            "updated_at": "2025-09-04T18:03:21.383464",
            "message": "Run data not found in new centralized system"
        }
    run_dir = Path(run['path'])
    status_path = run_dir / 'status.json'
    result = {"ts": ts, "phase": "unknown", "pct": 0}
    if status_path.exists():
        try:
            import json
            result.update(json.loads(status_path.read_text()))
        except Exception:
            pass
    return result

async def api_run_logs(request: Request, ts: str):
    """Get centralized logs for a run with pagination."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        offset = int(request.query_params.get('offset', '0'))
        limit = int(request.query_params.get('limit', '500'))
    except Exception:
        offset, limit = 0, 500
    
    # Try centralized logs first
    from .centralized_logging import get_run_logs
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    
    print(f"DEBUG: Looking for logs for run {ts}, offset={offset}, limit={limit}")
    
    # Find project and branch for this run
    projects_root = user_workspace / 'projects'
    if projects_root.exists():
        for proj in projects_root.iterdir():
            if not proj.is_dir():
                continue
            branches_dir = proj / 'branches'
            if not branches_dir.exists():
                continue
            for branch_dir in branches_dir.iterdir():
                if not branch_dir.is_dir():
                    continue
                # Check if this run exists in this branch by looking for log file
                log_file = branch_dir / 'logs' / f"{ts}.jsonl"
                if log_file.exists():
                    print(f"DEBUG: Found log file at {log_file}")
                    logs_result = get_run_logs(proj, branch_dir.name, ts, offset, limit)
                    print(f"DEBUG: Logs result: {len(logs_result.get('logs', []))} logs, next_offset={logs_result.get('next_offset', offset)}")
                    return logs_result
                    
    print(f"DEBUG: No centralized logs found for run {ts}")
    
    # Fallback to old system
    print(f"DEBUG: Trying fallback to old system for run {ts}")
    run = indexer.get_run_by_ts(ts)
    if not run:
        print(f"DEBUG: No run found in old system, returning empty logs")
        # Return empty logs with proper next_offset to prevent infinite polling
        return {
            "lines": [],
            "offset": offset,
            "next_offset": offset,  # Same offset indicates no new logs
            "has_more": False
        }
    log_path = Path(run['path']) / 'runs' / 'orchestrator.log.jsonl'
    next_offset = offset
    lines = []
    if log_path.exists():
        with open(log_path, 'rb') as f:
            f.seek(offset)
            for _ in range(limit):
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                next_offset = f.tell()
                try:
                    lines.append(__import__('json').loads(line.decode('utf-8').strip()))
                except Exception:
                    lines.append({"timestamp":"", "phase":"", "level":"info", "message": line.decode('utf-8','ignore').strip(), "meta":{}})
    return {"logs": lines, "next_offset": next_offset}
