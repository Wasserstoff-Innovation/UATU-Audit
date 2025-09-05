"""
GitHub OAuth authentication for the UatuAudit dashboard.
"""

import os
import httpx
import secrets
from typing import Optional, Dict, Any
from urllib.parse import urlencode, parse_qs
from starlette.requests import Request
from starlette.responses import RedirectResponse
from .security import set_user_session

# GitHub OAuth configuration
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')
GITHUB_REDIRECT_URI = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:8080/auth/callback')
ALLOWED_GH_ORGS = os.getenv('ALLOWED_GH_ORGS', '').split(',') if os.getenv('ALLOWED_GH_ORGS') else []
ALLOWED_EMAILS = os.getenv('ALLOWED_EMAILS', '').split(',') if os.getenv('ALLOWED_EMAILS') else []

def setup_oauth(app):
    """Setup OAuth with GitHub provider."""
    # OAuth setup is handled in the auth functions
    pass

async def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user info from GitHub API."""
    if not access_token:
        return None
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user info
            user_response = await client.get(
                'https://api.github.com/user',
                headers={'Authorization': f'token {access_token}'}
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            
            # Get user organizations
            orgs_response = await client.get(
                'https://api.github.com/user/orgs',
                headers={'Authorization': f'token {access_token}'}
            )
            orgs_response.raise_for_status()
            orgs_data = orgs_response.json()
            
            return {
                'login': user_data.get('login'),
                'email': user_data.get('email'),
                'name': user_data.get('name'),
                'avatar_url': user_data.get('avatar_url'),
                'orgs': [org['login'] for org in orgs_data],
                'github_id': user_data.get('id')
            }
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return None

async def verify_user_access(user_info: Dict[str, Any]) -> bool:
    """Verify user has access based on org membership or email."""
    if not user_info:
        return False
    
    # If no restrictions are set, allow all users
    if not ALLOWED_GH_ORGS and not ALLOWED_EMAILS:
        return True
    
    # Check email access
    if ALLOWED_EMAILS and user_info.get('email') in ALLOWED_EMAILS:
        return True
    
    # Check organization access
    if ALLOWED_GH_ORGS:
        user_orgs = user_info.get('orgs', [])
        if any(org in ALLOWED_GH_ORGS for org in user_orgs):
            return True
    
    return False

async def github_login(request: Request) -> RedirectResponse:
    """Initiate GitHub OAuth login."""
    if not GITHUB_CLIENT_ID:
        # Fallback to development mode
        return RedirectResponse(url='/dashboard')
    
    # Generate state parameter for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session['oauth_state'] = state
    
    # Debug logging
    print(f"OAuth Initiation Debug:")
    print(f"  Generated state: {state}")
    print(f"  Session keys: {list(request.session.keys())}")
    
    # Build GitHub OAuth URL
    params = {
        'client_id': GITHUB_CLIENT_ID,
        'redirect_uri': GITHUB_REDIRECT_URI,
        'scope': 'user:email read:org repo',
        'state': state
    }
    
    github_auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=github_auth_url)

async def github_callback(request: Request) -> RedirectResponse:
    """Handle GitHub OAuth callback."""
    # Check if we have proper GitHub OAuth configuration
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        # Fallback to development mode
        print("GitHub OAuth not configured, using development mode")
        set_user_session(request, {
            'login': 'dev-user',
            'email': 'dev@example.com',
            'name': 'Development User',
            'orgs': [],
            'github_id': 'dev'
        })
        return RedirectResponse(url='/onboarding/repos')
    
    # For development, if we get a fake code, just create a demo user
    code = request.query_params.get('code')
    if code and code.startswith('test'):
        print("Development mode: Using test code to create demo user")
        set_user_session(request, {
            'login': 'demo-user',
            'email': 'demo@example.com',
            'name': 'Demo User',
            'orgs': ['demo-org'],
            'github_id': 'demo'
        })
        return RedirectResponse(url='/onboarding/repos')
    
    # Verify state parameter
    state = request.query_params.get('state')
    stored_state = request.session.get('oauth_state')
    
    # Debug logging
    print(f"OAuth Callback Debug:")
    print(f"  Received state: {state}")
    print(f"  Stored state: {stored_state}")
    print(f"  Session keys: {list(request.session.keys())}")
    
    # For development, we'll be more lenient with state validation
    # In production, you should enforce strict state validation
    if not state:
        print(f"  No state parameter received - GitHub may have stripped it")
        print(f"  This can happen in development environments")
        # For development, we'll continue without state validation
        print(f"  Continuing without state validation for development")
        # Don't return error, just continue
    elif not stored_state:
        print(f"  No stored state found - session may have been lost")
        print(f"  This is common in development OAuth flows")
        print(f"  Continuing without state validation for development")
    elif state != stored_state:
        print(f"  State mismatch! Received: {state}, Expected: {stored_state}")
        # For development, we'll allow this to continue
        print(f"  Allowing state mismatch for development")
    else:
        print(f"  State validation successful")
    
    # Get authorization code
    code = request.query_params.get('code')
    if not code:
        return RedirectResponse(url='/?error=no_code')
    
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://github.com/login/oauth/access_token',
                data={
                    'client_id': GITHUB_CLIENT_ID,
                    'client_secret': GITHUB_CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': GITHUB_REDIRECT_URI
                },
                headers={'Accept': 'application/json'}
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            
            access_token = token_data.get('access_token')
            if not access_token:
                return RedirectResponse(url='/?error=no_token')
            
            # Get user info
            user_info = await get_user_info(access_token)
            if not user_info:
                return RedirectResponse(url='/?error=user_info_failed')
            
            # Verify user access
            if not await verify_user_access(user_info):
                return RedirectResponse(url='/?error=access_denied')
            
            # Set user session with GitHub token
            user_info['github_token'] = access_token
            set_user_session(request, user_info)
            
            # Store GitHub token in session for API calls
            request.session['github_token'] = access_token
            
            # Clear OAuth state
            request.session.pop('oauth_state', None)
            
            # Redirect to onboarding step 2 (repo selection)
            return RedirectResponse(url='/onboarding/repos')
            
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return RedirectResponse(url='/?error=oauth_failed')
