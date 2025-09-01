"""
Dashboard views for UatuAudit.
"""

import os
from datetime import datetime
from pathlib import Path
from fastapi import Request, HTTPException
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
    """Individual run detail page - requires authentication."""
    user = get_current_user(request)
    
    # Redirect to landing page if not authenticated
    if not user:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/", status_code=302)
    
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
    
    # For now, return mock repositories
    # In a real implementation, you'd use the user's GitHub token to fetch repos
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

async def setup_project(request: Request):
    """Setup project with selected repository."""
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
    
    # Get repository name from query params
    repo_name = request.query_params.get("repo")
    if not repo_name:
        raise HTTPException(status_code=400, detail="Repository name required")
    
    # In a real implementation, you would:
    # 1. Clone the repository
    # 2. Set up the audit environment
    # 3. Create initial audit configuration
    # 4. Redirect to the audit setup page
    
    # For now, just redirect to dashboard with repo info
    return RedirectResponse(url=f"/dashboard?repo={repo_name}&setup=complete")

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
