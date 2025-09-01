"""
Main dashboard server for UatuAudit.
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
# from .auth import setup_oauth
from .security import setup_sessions
from .views import (
    github_auth, auth_callback, logout,
    runs_page, run_detail, portfolio_page,
    download_pdf, download_portfolio_pdf, download_csv,
    health_check, landing_page, onboarding_repos, api_github_repos, test_oauth, setup_project
)
# Temporarily disable wallet auth imports until dependencies are installed
# from .wallet_auth import authenticate_wallet, link_github_to_wallet, logout_user
# from .models import connect_to_mongodb, close_mongodb_connection

# Create FastAPI app
app = FastAPI(
    title="UatuAudit Dashboard",
    description="Read-only web UI for browsing audit results",
    version="1.0.0"
)

# Setup middleware
setup_sessions(app)
# Temporarily disable OAuth setup until auth module is fixed
# setup_oauth(app)

# Mount static files
app.mount("/static", StaticFiles(directory="auditor/dashboard/static"), name="static")

# Routes
app.add_api_route("/", landing_page, methods=["GET"])  # Landing page as main entry
app.add_api_route("/dashboard", runs_page, methods=["GET"])  # Dashboard requires auth
app.add_api_route("/auth/github", github_auth, methods=["GET"])
app.add_api_route("/auth/callback", auth_callback, methods=["GET"])
app.add_api_route("/logout", logout, methods=["GET"])
app.add_api_route("/run/{ts}", run_detail, methods=["GET"])
app.add_api_route("/portfolio", portfolio_page, methods=["GET"])
app.add_api_route("/download/pdf/{ts}", download_pdf, methods=["GET"])
app.add_api_route("/download/portfolio/pdf", download_portfolio_pdf, methods=["GET"])
app.add_api_route("/download/portfolio/csv", download_csv, methods=["GET"])
app.add_api_route("/onboarding/repos", onboarding_repos, methods=["GET"])
app.add_api_route("/api/github/repos", api_github_repos, methods=["GET"])
app.add_api_route("/setup-project", setup_project, methods=["GET"])
app.add_api_route("/test-oauth", test_oauth, methods=["GET"])
app.add_api_route("/health", health_check, methods=["GET"])

# Temporarily create simple wallet auth endpoints
from fastapi import HTTPException
from fastapi.responses import JSONResponse

@app.post("/api/auth/wallet")
async def authenticate_wallet_simple(request: Request):
    """Temporary wallet authentication without MongoDB"""
    try:
        body = await request.json()
        wallet_address = body.get('wallet_address', '').lower()
        signature = body.get('signature', '')
        message = body.get('message', '')
        
        if not wallet_address or not signature or not message:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Simple session creation (using request session for now)
        session_id = f"temp_{wallet_address}_{hash(signature) % 10000}"
        
        # Store in request session
        request.session['wallet_address'] = wallet_address
        request.session['session_id'] = session_id
        request.session['authenticated'] = True
        
        return JSONResponse({
            'success': True,
            'session_id': session_id,
            'user': {
                'wallet_address': wallet_address,
                'name': f"User {wallet_address[:8]}"
            },
            'expires_at': '2024-12-31T23:59:59Z'  # Temporary
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/logout")
async def logout_simple(request: Request):
    """Simple logout"""
    request.session.clear()
    return JSONResponse({'success': True, 'message': 'Logged out'})

@app.get("/api/audits/history")
async def get_audit_history(request: Request):
    """Get user audit history (mock data for now)"""
    wallet_address = request.session.get('wallet_address')
    if not wallet_address:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Return mock audit data
    mock_audits = [
        {
            'id': '1',
            'repo_name': 'Sample',
            'branch': 'main',
            'status': 'completed',
            'security_score': 90,
            'created_at': '2024-09-01T10:00:00Z',
            'pdf_path': '/sample.pdf'
        },
        {
            'id': '2', 
            'repo_name': 'Sensitive',
            'branch': 'main',
            'status': 'completed',
            'security_score': 93,
            'created_at': '2024-09-01T11:00:00Z',
            'pdf_path': '/sensitive.pdf'
        }
    ]
    
    return JSONResponse(mock_audits)

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    return RedirectResponse(url="/static/favicon.ico")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "auditor.dashboard.server:app",
        host=host,
        port=port,
        reload=False
    )
