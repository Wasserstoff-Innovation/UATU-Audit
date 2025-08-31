"""
Main dashboard server for UatuAudit.
"""

import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware
from .auth import setup_oauth
from .security import setup_sessions
from .views import (
    login_page, github_auth, auth_callback, logout,
    runs_page, run_detail, portfolio_page,
    download_pdf, download_portfolio_pdf, download_csv,
    health_check, landing_page
)

# Create FastAPI app
app = FastAPI(
    title="UatuAudit Dashboard",
    description="Read-only web UI for browsing audit results",
    version="1.0.0"
)

# Setup middleware
setup_sessions(app)
setup_oauth(app)

# Mount static files
app.mount("/static", StaticFiles(directory="auditor/dashboard/static"), name="static")

# Routes
app.add_api_route("/", landing_page, methods=["GET"])  # Landing page as main entry
app.add_api_route("/dashboard", runs_page, methods=["GET"])  # Dashboard requires auth
app.add_api_route("/login", login_page, methods=["GET"])
app.add_api_route("/auth/github", github_auth, methods=["GET"])
app.add_api_route("/auth/callback", auth_callback, methods=["GET"])
app.add_api_route("/logout", logout, methods=["GET"])
app.add_api_route("/run/{ts}", run_detail, methods=["GET"])
app.add_api_route("/portfolio", portfolio_page, methods=["GET"])
app.add_api_route("/download/pdf/{ts}", download_pdf, methods=["GET"])
app.add_api_route("/download/portfolio/pdf", download_portfolio_pdf, methods=["GET"])
app.add_api_route("/download/portfolio/csv", download_csv, methods=["GET"])
app.add_api_route("/health", health_check, methods=["GET"])

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
