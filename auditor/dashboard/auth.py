"""
GitHub OAuth authentication for the UatuAudit dashboard.
Simplified version for development.
"""

import os
from typing import Optional, Dict, Any
from starlette.requests import Request
from starlette.responses import RedirectResponse

# Simplified OAuth configuration for development
def setup_oauth(app):
    """Setup OAuth with GitHub provider."""
    # For now, we'll skip OAuth setup to get the dashboard running
    # This can be enhanced later with proper OAuth integration
    pass

async def get_user_info(token: str) -> Optional[Dict[str, Any]]:
    """Get user info from GitHub API."""
    # Simplified for development
    return {
        'login': 'dev-user',
        'email': 'dev@example.com',
        'orgs': []
    }

async def verify_user_access(user_info: Dict[str, Any]) -> bool:
    """Verify user has access based on org membership or email."""
    # For development, allow all users
    return True

async def github_login(request: Request) -> RedirectResponse:
    """Initiate GitHub OAuth login."""
    # Simplified for development - redirect to dashboard
    return RedirectResponse(url='/')

async def github_callback(request: Request) -> Optional[Dict[str, Any]]:
    """Handle GitHub OAuth callback."""
    # Simplified for development
    return {
        'user': 'dev-user',
        'email': 'dev@example.com',
        'orgs': [],
        'ts': 1234567890
    }
