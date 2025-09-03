#!/usr/bin/env python3
"""
UatuAudit Backend API Server
Handles GitHub OAuth, webhooks, and audit processing
"""

import os
import json
import hmac
import hashlib
import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from jose import JWTError, jwt
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
import git

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./uatu_audit.db")

# Database setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(String, unique=True, index=True)
    username = Column(String, index=True)
    email = Column(String)
    access_token = Column(String)  # Encrypted
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditJob(Base):
    __tablename__ = "audit_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    repo_name = Column(String)
    branch = Column(String)
    commit_sha = Column(String)
    status = Column(String, default="pending")  # pending, running, completed, failed
    results = Column(Text)  # JSON string
    pdf_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    repo_name = Column(String)
    event_type = Column(String)
    payload = Column(Text)  # JSON string
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI(title="UatuAudit API", description="Backend for UatuAudit security auditing platform")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class GitHubOAuthResponse(BaseModel):
    access_token: str
    user_info: dict

class AuditRequest(BaseModel):
    repo_name: str
    branch: str
    commit_sha: Optional[str] = None

class MockAuditRequest(BaseModel):
    contract_file: str  # Which example file to audit

# Helper functions
def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

def verify_webhook_signature(request_body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature"""
    if not GITHUB_WEBHOOK_SECRET:
        return False
    
    expected_signature = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected_signature}", signature)

async def get_github_user_info(access_token: str) -> dict:
    """Get user info from GitHub API"""
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"token {access_token}"}
        response = await client.get("https://api.github.com/user", headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")
        return response.json()

def run_audit_on_contract(contract_path: str, output_dir: str) -> Dict[str, Any]:
    """Run security audit on a Solidity contract"""
    try:
        # This is a simplified audit - replace with actual audit tools
        audit_results = {
            "contract_path": contract_path,
            "timestamp": datetime.utcnow().isoformat(),
            "findings": [],
            "security_score": 85,  # Mock score
            "gas_optimization": [],
            "best_practices": []
        }
        
        # Read contract content
        with open(contract_path, 'r') as f:
            contract_content = f.read()
        
        # Simple pattern-based analysis (replace with real audit tools)
        if "onlyOwner" in contract_content:
            audit_results["findings"].append({
                "severity": "INFO",
                "title": "Access Control Found",
                "description": "Contract uses onlyOwner modifier for access control",
                "line": None
            })
        
        if "require(" in contract_content:
            audit_results["findings"].append({
                "severity": "GOOD",
                "title": "Input Validation Present",
                "description": "Contract uses require statements for input validation",
                "line": None
            })
        
        if "transfer(" in contract_content.lower():
            audit_results["findings"].append({
                "severity": "WARNING",
                "title": "Potential Reentrancy Risk",
                "description": "Contract contains transfer operations - ensure reentrancy protection",
                "line": None
            })
        
        # Save results
        results_path = os.path.join(output_dir, "audit_results.json")
        with open(results_path, 'w') as f:
            json.dump(audit_results, f, indent=2)
        
        return audit_results
        
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

def generate_audit_pdf(audit_results: Dict[str, Any], output_path: str) -> str:
    """Generate PDF report from audit results"""
    try:
        # Mock PDF generation - replace with actual PDF library
        pdf_content = f"""
        UatuAudit Security Report
        Generated: {audit_results.get('timestamp', 'Unknown')}
        
        Contract: {audit_results.get('contract_path', 'Unknown')}
        Security Score: {audit_results.get('security_score', 0)}/100
        
        Findings:
        """
        
        for finding in audit_results.get('findings', []):
            pdf_content += f"""
        - {finding['severity']}: {finding['title']}
          {finding['description']}
            """
        
        # Write mock PDF content (replace with actual PDF generation)
        with open(output_path, 'w') as f:
            f.write(pdf_content)
        
        return output_path
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

# API Routes

@app.get("/")
async def root():
    return {"message": "UatuAudit API Server", "status": "running"}

@app.get("/auth/github")
async def github_oauth_callback(code: str, state: Optional[str] = None, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"}
            )
            
            if token_response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to get access token")
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=400, detail="No access token received")
        
        # Get user info
        user_info = await get_github_user_info(access_token)
        
        # Store or update user in database
        user = db.query(User).filter(User.github_id == str(user_info["id"])).first()
        if not user:
            user = User(
                github_id=str(user_info["id"]),
                username=user_info["login"],
                email=user_info.get("email"),
                access_token=access_token  # Should encrypt this
            )
            db.add(user)
        else:
            user.access_token = access_token  # Should encrypt this
        
        db.commit()
        
        # Create JWT token
        jwt_payload = {
            "user_id": user.id,
            "github_id": user.github_id,
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        jwt_token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")
        
        # Return to frontend with token
        return RedirectResponse(
            url=f"{FRONTEND_URL}?token={jwt_token}&user={user_info['login']}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audit/mock")
async def start_mock_audit(
    request: MockAuditRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """Start a mock audit using example Solidity files"""
    try:
        # Map contract files to actual paths
        contract_files = {
            "sample": "/Users/soneshwar/Desktop/codes/UatuAudit/examples/sample.sol",
            "sensitive": "/Users/soneshwar/Desktop/codes/UatuAudit/examples/sensitive.sol"
        }
        
        if request.contract_file not in contract_files:
            raise HTTPException(status_code=400, detail="Invalid contract file")
        
        contract_path = contract_files[request.contract_file]
        
        # Create audit job
        audit_job = AuditJob(
            user_id=current_user["user_id"],
            repo_name=f"mock/{request.contract_file}",
            branch="main",
            commit_sha="mock_commit",
            status="running"
        )
        db.add(audit_job)
        db.commit()
        
        # Run audit in background
        background_tasks.add_task(run_mock_audit_background, audit_job.id, contract_path)
        
        return {"job_id": audit_job.id, "status": "started", "message": "Mock audit started"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def run_mock_audit_background(job_id: int, contract_path: str):
    """Background task to run mock audit"""
    db = SessionLocal()
    try:
        job = db.query(AuditJob).filter(AuditJob.id == job_id).first()
        if not job:
            return
        
        # Create output directory
        output_dir = f"./audit_outputs/job_{job_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Run audit
        audit_results = run_audit_on_contract(contract_path, output_dir)
        
        # Generate PDF
        pdf_path = os.path.join(output_dir, "audit_report.pdf")
        generate_audit_pdf(audit_results, pdf_path)
        
        # Update job
        job.status = "completed"
        job.results = json.dumps(audit_results)
        job.pdf_path = pdf_path
        job.completed_at = datetime.utcnow()
        
        db.commit()
        
    except Exception as e:
        job.status = "failed"
        job.results = json.dumps({"error": str(e)})
        db.commit()
    finally:
        db.close()

@app.get("/api/audit/{job_id}")
async def get_audit_status(
    job_id: int,
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """Get audit job status and results"""
    job = db.query(AuditJob).filter(
        AuditJob.id == job_id,
        AuditJob.user_id == current_user["user_id"]
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Audit job not found")
    
    return {
        "id": job.id,
        "status": job.status,
        "repo_name": job.repo_name,
        "branch": job.branch,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "results": json.loads(job.results) if job.results else None,
        "has_pdf": bool(job.pdf_path)
    }

@app.get("/api/audit/{job_id}/pdf")
async def download_audit_pdf(
    job_id: int,
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """Download audit PDF report"""
    job = db.query(AuditJob).filter(
        AuditJob.id == job_id,
        AuditJob.user_id == current_user["user_id"]
    ).first()
    
    if not job or not job.pdf_path:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # Return file content (in production, use FileResponse)
    try:
        with open(job.pdf_path, 'r') as f:
            content = f.read()
        return {"pdf_content": content, "filename": f"audit_report_{job_id}.pdf"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF file not found")

@app.post("/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub webhook events"""
    try:
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        
        if not verify_webhook_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
        payload = json.loads(body.decode())
        event_type = request.headers.get("X-GitHub-Event")
        
        # Store webhook event
        webhook_event = WebhookEvent(
            repo_name=payload.get("repository", {}).get("full_name"),
            event_type=event_type,
            payload=json.dumps(payload)
        )
        db.add(webhook_event)
        db.commit()
        
        # Process push events
        if event_type == "push":
            # Trigger re-audit for active repositories
            # This would be implemented based on your requirements
            pass
        
        return {"status": "received"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/repos")
async def get_user_repos(current_user: dict = Depends(verify_jwt_token), db: Session = Depends(get_db)):
    """Get user's GitHub repositories"""
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"token {user.access_token}"}
            response = await client.get(
                "https://api.github.com/user/repos?sort=updated&per_page=100",
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch repositories")
            
            return response.json()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repos/{owner}/{repo}/branches")
async def get_repo_branches(
    owner: str,
    repo: str,
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    """Get repository branches"""
    user = db.query(User).filter(User.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"token {user.access_token}"}
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/branches",
                headers=headers
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch branches")
            
            return response.json()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)