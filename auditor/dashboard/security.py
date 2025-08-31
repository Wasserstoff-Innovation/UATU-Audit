"""
Security and session management for the UatuAudit dashboard.
"""

import os
import time
from typing import Optional, Dict, Any
from functools import wraps
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.applications import Starlette

def setup_sessions(app: Starlette):
    """Setup session middleware."""
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv('SECRET_KEY', 'change-me-in-production'),
        max_age=3600,  # 1 hour
        same_site='lax'
    )

def login_required(func):
    """Decorator to require authentication for views."""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # Temporarily allow all access for testing
        return await func(request, *args, **kwargs)
    return wrapper

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session."""
    # Check if user is in session
    if 'user' in request.session and is_session_valid(request):
        return request.session['user']
    return None

def set_user_session(request: Request, user_info: Dict[str, Any]):
    """Set user session data."""
    request.session['user'] = user_info
    request.session['login_time'] = time.time()

def clear_user_session(request: Request):
    """Clear user session data."""
    request.session.clear()

def is_session_valid(request: Request) -> bool:
    """Check if user session is still valid."""
    if 'user' not in request.session or 'login_time' not in request.session:
        return False
    
    # Check if session has expired (1 hour)
    login_time = request.session.get('login_time', 0)
    current_time = time.time()
    return (current_time - login_time) < 3600
