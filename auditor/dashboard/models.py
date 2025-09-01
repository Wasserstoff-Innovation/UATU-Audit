"""
MongoDB models for UatuAudit Dashboard
"""

import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel
import asyncio
from bson import ObjectId

# MongoDB connection
MONGODB_URL = os.getenv('MONGODB_URL', 'mongodb://localhost:27017/uatu_audit')

class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database = None

# Global database instance
db_instance = MongoDB()

async def connect_to_mongodb():
    """Connect to MongoDB database"""
    db_instance.client = AsyncIOMotorClient(MONGODB_URL)
    db_instance.database = db_instance.client.get_default_database()
    
    # Create indexes
    await create_indexes()
    print(f"Connected to MongoDB: {MONGODB_URL}")

async def close_mongodb_connection():
    """Close MongoDB connection"""
    if db_instance.client:
        db_instance.client.close()

async def create_indexes():
    """Create database indexes for performance"""
    if not db_instance.database:
        return
    
    # User indexes
    await db_instance.database.users.create_indexes([
        IndexModel("wallet_address", unique=True),
        IndexModel("github_id"),
        IndexModel("email"),
        IndexModel("created_at")
    ])
    
    # Audit job indexes
    await db_instance.database.audit_jobs.create_indexes([
        IndexModel("user_id"),
        IndexModel("wallet_address"),
        IndexModel("status"),
        IndexModel("created_at"),
        IndexModel("repo_name")
    ])
    
    # Session indexes
    await db_instance.database.sessions.create_indexes([
        IndexModel("wallet_address"),
        IndexModel("session_id", unique=True),
        IndexModel("expires_at")
    ])

def get_database():
    """Get database instance"""
    return db_instance.database

class User:
    """User model for wallet-based authentication"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('_id')
        self.wallet_address = data.get('wallet_address')
        self.github_id = data.get('github_id')
        self.github_username = data.get('github_username')
        self.email = data.get('email')
        self.name = data.get('name')
        self.avatar_url = data.get('avatar_url')
        self.github_access_token = data.get('github_access_token')
        self.created_at = data.get('created_at', datetime.utcnow())
        self.updated_at = data.get('updated_at', datetime.utcnow())
        self.is_active = data.get('is_active', True)
        
    @classmethod
    async def create(cls, wallet_address: str, **kwargs) -> 'User':
        """Create a new user"""
        db = get_database()
        user_data = {
            'wallet_address': wallet_address.lower(),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'is_active': True,
            **kwargs
        }
        
        result = await db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        return cls(user_data)
    
    @classmethod
    async def get_by_wallet(cls, wallet_address: str) -> Optional['User']:
        """Get user by wallet address"""
        db = get_database()
        user_data = await db.users.find_one({'wallet_address': wallet_address.lower()})
        return cls(user_data) if user_data else None
    
    @classmethod
    async def get_by_github_id(cls, github_id: str) -> Optional['User']:
        """Get user by GitHub ID"""
        db = get_database()
        user_data = await db.users.find_one({'github_id': github_id})
        return cls(user_data) if user_data else None
    
    async def update(self, **kwargs) -> 'User':
        """Update user data"""
        db = get_database()
        update_data = {
            'updated_at': datetime.utcnow(),
            **kwargs
        }
        
        await db.users.update_one(
            {'_id': self.id},
            {'$set': update_data}
        )
        
        # Update local data
        for key, value in update_data.items():
            setattr(self, key, value)
        
        return self
    
    async def link_github(self, github_data: Dict[str, Any], access_token: str):
        """Link GitHub account to wallet"""
        return await self.update(
            github_id=str(github_data.get('id')),
            github_username=github_data.get('login'),
            email=github_data.get('email'),
            name=github_data.get('name'),
            avatar_url=github_data.get('avatar_url'),
            github_access_token=access_token
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            'id': str(self.id),
            'wallet_address': self.wallet_address,
            'github_id': self.github_id,
            'github_username': self.github_username,
            'email': self.email,
            'name': self.name,
            'avatar_url': self.avatar_url,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'is_active': self.is_active
        }

class AuditJob:
    """Audit job model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('_id')
        self.user_id = data.get('user_id')
        self.wallet_address = data.get('wallet_address')
        self.repo_name = data.get('repo_name')
        self.branch = data.get('branch')
        self.commit_sha = data.get('commit_sha')
        self.status = data.get('status', 'pending')  # pending, running, completed, failed
        self.results = data.get('results')
        self.security_score = data.get('security_score')
        self.pdf_path = data.get('pdf_path')
        self.created_at = data.get('created_at', datetime.utcnow())
        self.completed_at = data.get('completed_at')
        self.error_message = data.get('error_message')
    
    @classmethod
    async def create(cls, user_id: str, wallet_address: str, **kwargs) -> 'AuditJob':
        """Create a new audit job"""
        db = get_database()
        job_data = {
            'user_id': user_id,
            'wallet_address': wallet_address.lower(),
            'created_at': datetime.utcnow(),
            'status': 'pending',
            **kwargs
        }
        
        result = await db.audit_jobs.insert_one(job_data)
        job_data['_id'] = result.inserted_id
        return cls(job_data)
    
    @classmethod
    async def get_by_user(cls, user_id: str, limit: int = 50) -> List['AuditJob']:
        """Get audit jobs for a user"""
        db = get_database()
        cursor = db.audit_jobs.find({'user_id': user_id}).sort('created_at', -1).limit(limit)
        jobs = []
        async for job_data in cursor:
            jobs.append(cls(job_data))
        return jobs
    
    @classmethod
    async def get_by_wallet(cls, wallet_address: str, limit: int = 50) -> List['AuditJob']:
        """Get audit jobs for a wallet address"""
        db = get_database()
        cursor = db.audit_jobs.find({'wallet_address': wallet_address.lower()}).sort('created_at', -1).limit(limit)
        jobs = []
        async for job_data in cursor:
            jobs.append(cls(job_data))
        return jobs
    
    @classmethod
    async def get_by_id(cls, job_id: str) -> Optional['AuditJob']:
        """Get audit job by ID"""
        db = get_database()
        try:
            job_data = await db.audit_jobs.find_one({'_id': ObjectId(job_id)})
            return cls(job_data) if job_data else None
        except:
            return None
    
    async def update_status(self, status: str, **kwargs) -> 'AuditJob':
        """Update job status"""
        db = get_database()
        update_data = {'status': status, **kwargs}
        
        if status == 'completed':
            update_data['completed_at'] = datetime.utcnow()
        
        await db.audit_jobs.update_one(
            {'_id': self.id},
            {'$set': update_data}
        )
        
        # Update local data
        for key, value in update_data.items():
            setattr(self, key, value)
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'id': str(self.id),
            'user_id': self.user_id,
            'wallet_address': self.wallet_address,
            'repo_name': self.repo_name,
            'branch': self.branch,
            'commit_sha': self.commit_sha,
            'status': self.status,
            'results': self.results,
            'security_score': self.security_score,
            'pdf_path': self.pdf_path,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'error_message': self.error_message
        }

class UserSession:
    """User session model for wallet-based auth"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('_id')
        self.session_id = data.get('session_id')
        self.wallet_address = data.get('wallet_address')
        self.user_id = data.get('user_id')
        self.github_connected = data.get('github_connected', False)
        self.created_at = data.get('created_at', datetime.utcnow())
        self.expires_at = data.get('expires_at')
        self.last_activity = data.get('last_activity', datetime.utcnow())
    
    @classmethod
    async def create(cls, session_id: str, wallet_address: str, user_id: str, expires_at: datetime) -> 'UserSession':
        """Create a new session"""
        db = get_database()
        session_data = {
            'session_id': session_id,
            'wallet_address': wallet_address.lower(),
            'user_id': user_id,
            'created_at': datetime.utcnow(),
            'expires_at': expires_at,
            'last_activity': datetime.utcnow(),
            'github_connected': False
        }
        
        result = await db.sessions.insert_one(session_data)
        session_data['_id'] = result.inserted_id
        return cls(session_data)
    
    @classmethod
    async def get_by_session_id(cls, session_id: str) -> Optional['UserSession']:
        """Get session by session ID"""
        db = get_database()
        session_data = await db.sessions.find_one({'session_id': session_id})
        return cls(session_data) if session_data else None
    
    async def update_activity(self):
        """Update last activity timestamp"""
        db = get_database()
        self.last_activity = datetime.utcnow()
        await db.sessions.update_one(
            {'_id': self.id},
            {'$set': {'last_activity': self.last_activity}}
        )
    
    async def set_github_connected(self, connected: bool = True):
        """Update GitHub connection status"""
        db = get_database()
        self.github_connected = connected
        await db.sessions.update_one(
            {'_id': self.id},
            {'$set': {'github_connected': connected}}
        )
    
    async def delete(self):
        """Delete session"""
        db = get_database()
        await db.sessions.delete_one({'_id': self.id})
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary"""
        return {
            'id': str(self.id),
            'session_id': self.session_id,
            'wallet_address': self.wallet_address,
            'user_id': self.user_id,
            'github_connected': self.github_connected,
            'created_at': self.created_at,
            'expires_at': self.expires_at,
            'last_activity': self.last_activity
        }