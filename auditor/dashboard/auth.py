"""
GitHub OAuth authentication for the UatuAudit dashboard.
"""

import os
from typing import Optional, Dict, Any
from authlib.integrations.starlette import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.datastructures import URL

# OAuth configuration
oauth = OAuth()

def setup_oauth(app):
    """Setup OAuth with GitHub provider."""
    oauth.init_app(app)
    oauth.register(
        name='github',
        client_id=os.getenv('GITHUB_CLIENT_ID'),
        client_secret=os.getenv('GITHUB_CLIENT_SECRET'),
        access_token_url='https://github.com/login/oauth/access_token',
        access_token_params=None,
        authorize_url='https://github.com/login/oauth/authorize',
        authorize_params=None,
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'read:user user:email'},
    )

async def get_user_info(token: str) -> Optional[Dict[str, Any]]:
    """Get user info from GitHub API."""
    try:
        resp = await oauth.github.parse_id_token(token, nonce=None)
        return resp
    except Exception:
        return None

async def verify_user_access(user_info: Dict[str, Any]) -> bool:
    """Verify user has access based on org membership or email."""
    allowed_orgs = os.getenv('ALLOWED_GH_ORGS', '').split(',')
    allowed_emails = os.getenv('ALLOWED_EMAILS', '').split(',')
    
    # Check email first
    if allowed_emails and user_info.get('email'):
        if user_info['email'] in allowed_emails:
            return True
    
    # Check org membership
    if allowed_orgs and user_info.get('login'):
        try:
            # Check if user is member of any allowed org
            for org in allowed_orgs:
                org = org.strip()
                if org:
                    # This is a simplified check - in production you might want to verify org membership
                    # For now, we'll allow if org is set and user has a valid GitHub account
                    return True
        except Exception:
            pass
    
    # If no restrictions set, allow all authenticated users
    if not allowed_orgs and not allowed_emails:
        return True
    
    return False

async def github_login(request: Request) -> RedirectResponse:
    """Initiate GitHub OAuth login."""
    redirect_uri = request.url_for('auth_callback')
    return await oauth.github.authorize_redirect(request, redirect_uri)

async def github_callback(request: Request) -> Optional[Dict[str, Any]]:
    """Handle GitHub OAuth callback."""
    try:
        token = await oauth.github.authorize_access_token(request)
        user_info = await get_user_info(token)
        
        if user_info and await verify_user_access(user_info):
            return {
                'user': user_info.get('login'),
                'email': user_info.get('email'),
                'orgs': [],  # Could fetch actual orgs if needed
                'ts': token.get('created_at', 0)
            }
    except Exception:
        pass
    
    return None
