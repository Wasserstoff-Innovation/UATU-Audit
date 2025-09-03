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
    """Run detail page with timeline and streaming logs."""
    return templates.TemplateResponse("run_detail.html", {"request": request})

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
    
    # Redirect to landing page if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
    
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
    print(f"=== api_github_repos called ===")
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
    
    if not github_token:
        # Return mock repositories for demo
        return await get_mock_repositories(user)
    
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
            
            if repos_response.status_code != 200:
                print(f"GitHub API error: {repos_response.status_code} - {repos_response.text}")
                return await get_mock_repositories(user)
            
            repos_data = repos_response.json()
            
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
            
            return formatted_repos
            
    except Exception as e:
        print(f"Error fetching GitHub repositories: {e}")
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
    print(f"=== api_github_branches called ===")
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

async def run_audit_process(audit_path: Path, audit_id: str, user_login: str, repo_name: str | None = None, branch_name: str | None = None) -> dict:
    """Run the UatuAudit process on cloned repository with test generation."""
    try:
        # Import the Orchestrator from core
        from ..core import Orchestrator
        
        # Determine repo/branch for project layout
        repo_name = repo_name or audit_path.name
        branch_name = branch_name or 'main'

        user_workspace = get_user_workspace(user_login)
        project_id = (repo_name or 'adhoc').replace('/', '~')
        project_root = user_workspace / 'projects' / project_id
        branch_root = project_root / 'branches' / (branch_name or 'main')
        (branch_root / 'shared').mkdir(parents=True, exist_ok=True)

        # Orchestrator out_root will be branch_root; it will create runs/<ts>
        audit_output = branch_root
        
        # Update status to running
        status_file = audit_output / f"{audit_id}_status.json"
        status_data = {
            "id": audit_id,
            "user": user_login,
            "status": "running",
            "phase": "analysis",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "repo_path": str(audit_path),
        }
        
        with open(status_file, 'w') as f:
            import json
            json.dump(status_data, f, indent=2)
        
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
        
        # Update status to test generation
        status_data["phase"] = "test_generation"
        status_data["updated_at"] = datetime.utcnow().isoformat()
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
        
        # Run the audit process (this includes test generation)
        result_path = orchestrator.run()
        
        # Update status to completed
        status_data["phase"] = "completed"
        status_data["status"] = "completed"
        status_data["updated_at"] = datetime.utcnow().isoformat()
        status_data["result_path"] = str(result_path)
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)
        
        # Create audit result metadata
        audit_result = {
            "id": audit_id,
            "user": user_login,
            "status": "completed",
            "created_at": datetime.utcnow().isoformat(),
            "result_path": str(result_path),
            "repo_path": str(audit_path),
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
            json.dump(status_data, f, indent=2)
        with open(legacy_dir / f"{audit_id}_metadata.json", 'w') as f:
            json.dump(audit_result, f, indent=2)
        
        print(f"Audit completed for {audit_id}: {result_path}")
        return audit_result
        
    except Exception as e:
        print(f"Audit process failed for {audit_id}: {e}")
        # Update status to failed
        try:
            status_data["status"] = "failed"
            status_data["phase"] = "failed"
            status_data["error"] = str(e)
            status_data["updated_at"] = datetime.utcnow().isoformat()
            with open(status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
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
        
        # Start background process
        async def audit_workflow():
            try:
                # Update status to cloning
                print(f"Starting audit workflow for {audit_id}")
                
                # Clone repository
                clone_success = await clone_repository(repo_url, branch_name, repo_clone_path, github_token)
                
                if clone_success:
                    print(f"Clone successful for {audit_id}, starting audit process")
                    # Run audit process
                    audit_result = await run_audit_process(repo_clone_path, audit_id, user_login)
                    
                    # Update session with completed audit
                    # Note: In production, you'd want to store this in a database
                    print(f"Audit workflow completed for {audit_id}")
                else:
                    print(f"Clone failed for {audit_id}")
                    # Handle clone failure - could store error state
                    
            except Exception as e:
                print(f"Audit workflow failed for {audit_id}: {e}")
        
        # Start background task using asyncio
        async def _runner():
            await run_audit_process(repo_clone_path, audit_id, user_login, repo_name=repo_name, branch_name=branch_name)
        asyncio.create_task(_runner())
        
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
        with open(audit_metadata_path, 'r') as f:
            return json.load(f)
    else:
        # Return session info as fallback
        current_audit = request.session.get('current_audit', {})
        if current_audit.get('id') == audit_id:
            return current_audit
        else:
            raise HTTPException(status_code=404, detail="Audit not found")

async def api_list_user_audits(request: Request):
    """List all audits for current user."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user_workspace = get_user_workspace(user.get('login', 'demo-user'))
    audits_dir = user_workspace / "audits"
    
    audits = []
    if audits_dir.exists():
        import json
        for audit_folder in audits_dir.iterdir():
            if audit_folder.is_dir():
                metadata_file = audit_folder / f"{audit_folder.name}_metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            audit_data = json.load(f)
                            audits.append(audit_data)
                    except Exception as e:
                        print(f"Error loading audit metadata: {e}")
    
    return {"audits": sorted(audits, key=lambda x: x.get('created_at', ''), reverse=True)}

async def test_endpoint(request: Request):
    """Test endpoint for debugging."""
    print("=== test_endpoint called ===")
    return {"message": "Test endpoint working", "path": str(request.url)}

async def test_oauth(request: Request):
    """Test OAuth endpoint for development."""
    from .security import set_user_session
    
    # Create a test user session
    set_user_session(request, {
        'login': 'test-user',
        'email': 'test@example.com',
        'name': 'Test User',
        'orgs': ['test-org'],
        'github_id': 'test'
    })
    
    return RedirectResponse(url='/dashboard')

async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# --- New: Projects and runs listing (provisional grouping) ---
async def api_projects(request: Request):
    """List projects for current user. Provisional: groups available runs under a single 'adhoc' project if migration not done."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    # Scan user workspace projects
    ws = get_user_workspace(user.get('login','demo-user'))
    projects_root = ws / 'projects'
    projects = []
    if projects_root.exists():
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
                    runs_root = br / 'runs'
                    last_run = None
                    if runs_root.exists():
                        rdirs = [d for d in runs_root.iterdir() if d.is_dir()]
                        rdirs.sort(reverse=True)
                        if rdirs:
                            # try read risk.json for score/grade
                            risk = rdirs[0] / 'runs' / 'risk' / 'risk.json'
                            score = 0.0
                            grade = 'Info'
                            if risk.exists():
                                try:
                                    j = __import__('json').loads(risk.read_text())
                                    sc = j.get('summary',{})
                                    score = float(sc.get('overall',0.0))
                                    grade = sc.get('grade','Info')
                                except Exception:
                                    pass
                            last_run = {"ts": rdirs[0].name, "status": 'completed', "score": score, "grade": grade, "delta": 0.0}
                    branches.append({
                        "name": br.name,
                        "last_run": last_run,
                        "errors": 0,
                        "updated_at": datetime.utcnow().isoformat()+"Z"
                    })
            projects.append({
                "id": owner_repo,
                "owner_repo": owner_repo,
                "branches": branches,
                "settings": {"llm":"auto","journey_cap":5,"stress":"small"}
            })
    return {"projects": projects}

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
    """Return status for a given run timestamp."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    run = indexer.get_run_by_ts(ts)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
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
    """Tail JSONL logs for a run with byte offset and limit of lines."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        offset = int(request.query_params.get('offset', '0'))
        limit = int(request.query_params.get('limit', '500'))
    except Exception:
        offset, limit = 0, 500
    run = indexer.get_run_by_ts(ts)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
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
                    lines.append({"t":"", "phase":"", "level":"info", "msg": line.decode('utf-8','ignore').strip(), "meta":{}})
    return {"offset": next_offset, "lines": lines}
