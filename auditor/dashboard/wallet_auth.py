"""
Wallet-based authentication system for UatuAudit
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from .models import User, UserSession, get_database
import hashlib
import httpx

# Configuration
SESSION_DURATION_HOURS = int(os.getenv('SESSION_DURATION_HOURS', '24'))
GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')

def verify_wallet_signature(message: str, signature: str, wallet_address: str) -> bool:
    """
    Verify wallet signature for authentication
    This is a simplified version - in production you'd use proper crypto libraries
    """
    # For demo purposes, we'll accept any signature that contains the wallet address
    # In production, use proper signature verification like eth_account.messages
    return wallet_address.lower() in message.lower()

async def create_wallet_session(wallet_address: str, github_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Create a new wallet-based session"""
    
    # Get or create user
    user = await User.get_by_wallet(wallet_address)
    if not user:
        user = await User.create(
            wallet_address=wallet_address,
            name=f"User {wallet_address[:8]}"
        )
    
    # Link GitHub data if provided
    if github_data and 'access_token' in github_data:
        await user.link_github(github_data, github_data['access_token'])
    
    # Create session
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)
    
    session = await UserSession.create(
        session_id=session_id,
        wallet_address=wallet_address,
        user_id=str(user.id),
        expires_at=expires_at
    )
    
    if github_data:
        await session.set_github_connected(True)
    
    return {
        'session_id': session_id,
        'user': user.to_dict(),
        'expires_at': expires_at.isoformat(),
        'github_connected': bool(github_data)
    }

async def get_user_from_session(request: Request) -> Optional[Dict[str, Any]]:
    """Get user from session"""
    
    # Check for session in cookies or headers
    session_id = None
    
    # Try cookie first
    if 'session_id' in request.cookies:
        session_id = request.cookies['session_id']
    
    # Try Authorization header
    elif 'Authorization' in request.headers:
        auth_header = request.headers['Authorization']
        if auth_header.startswith('Bearer '):
            session_id = auth_header[7:]
    
    if not session_id:
        return None
    
    # Get session from database
    session = await UserSession.get_by_session_id(session_id)
    if not session or session.is_expired():
        return None
    
    # Update last activity
    await session.update_activity()
    
    # Get user
    user = await User.get_by_wallet(session.wallet_address)
    if not user:
        return None
    
    return {
        'user': user.to_dict(),
        'session': session.to_dict()
    }

async def authenticate_wallet(request: Request) -> Dict[str, Any]:
    """Authenticate wallet and create session"""
    
    try:
        body = await request.json()
        wallet_address = body.get('wallet_address', '').lower()
        signature = body.get('signature', '')
        message = body.get('message', '')
        
        if not wallet_address or not signature or not message:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        # Verify signature
        if not verify_wallet_signature(message, signature, wallet_address):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Create session
        session_data = await create_wallet_session(wallet_address)
        
        return {
            'success': True,
            'session_id': session_data['session_id'],
            'user': session_data['user'],
            'expires_at': session_data['expires_at']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def link_github_to_wallet(request: Request, github_code: str) -> Dict[str, Any]:
    """Link GitHub account to existing wallet session"""
    
    # Get current user session
    session_data = await get_user_from_session(request)
    if not session_data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_data = session_data['user']
    
    try:
        # Exchange GitHub code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://github.com/login/oauth/access_token',
                data={
                    'client_id': GITHUB_CLIENT_ID,
                    'client_secret': GITHUB_CLIENT_SECRET,
                    'code': github_code,
                    'redirect_uri': os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:8080/auth/callback')
                },
                headers={'Accept': 'application/json'}
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            
            access_token = token_data.get('access_token')
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to get GitHub access token")
            
            # Get GitHub user info
            user_response = await client.get(
                'https://api.github.com/user',
                headers={'Authorization': f'token {access_token}'}
            )
            user_response.raise_for_status()
            github_user = user_response.json()
            
            # Update user with GitHub info
            user = await User.get_by_wallet(user_data['wallet_address'])
            if user:
                await user.link_github(github_user, access_token)
                
                # Update session
                session = await UserSession.get_by_session_id(session_data['session']['session_id'])
                if session:
                    await session.set_github_connected(True)
                
                return {
                    'success': True,
                    'github_user': {
                        'login': github_user.get('login'),
                        'name': github_user.get('name'),
                        'email': github_user.get('email'),
                        'avatar_url': github_user.get('avatar_url')
                    }
                }
            
            raise HTTPException(status_code=404, detail="User not found")
            
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"GitHub API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def logout_user(request: Request) -> Dict[str, Any]:
    """Logout user and delete session"""
    
    session_data = await get_user_from_session(request)
    if not session_data:
        return {'success': True, 'message': 'Already logged out'}
    
    # Delete session
    session = await UserSession.get_by_session_id(session_data['session']['session_id'])
    if session:
        await session.delete()
    
    return {'success': True, 'message': 'Logged out successfully'}

def require_auth(require_github: bool = False):
    """Decorator to require authentication"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            session_data = await get_user_from_session(request)
            if not session_data:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if require_github and not session_data['session']['github_connected']:
                raise HTTPException(status_code=403, detail="GitHub connection required")
            
            # Add user data to request state
            request.state.user = session_data['user']
            request.state.session = session_data['session']
            
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator