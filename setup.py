#!/usr/bin/env python3
"""
UatuAudit Setup Script
Complete setup for the UatuAudit platform
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_banner():
    print("""
🔒 UatuAudit Platform Setup
============================
Setting up your complete security audit platform with:
✅ Backend API with GitHub OAuth & webhooks
✅ Frontend dashboard with wallet integration
✅ Mock testing with existing Solidity contracts
✅ PDF report generation
    """)

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("\n📦 Installing Python dependencies...")
    
    requirements = [
        'fastapi==0.104.1',
        'uvicorn[standard]==0.24.0',
        'httpx==0.25.2',
        'python-jose[cryptography]==3.3.0',
        'python-multipart==0.0.6',
        'sqlalchemy==2.0.23',
        'python-dotenv==1.0.0',
        'GitPython==3.1.40',
        'pydantic==2.5.0'
    ]
    
    for req in requirements:
        try:
            print(f"   Installing {req.split('==')[0]}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', req], 
                         check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {req}")
            return False
    
    print("✅ All dependencies installed successfully!")
    return True

def setup_environment():
    """Setup environment configuration"""
    print("\n⚙️ Setting up environment configuration...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print("✅ .env file created from .env.example")
        else:
            # Create basic .env file
            env_content = """# UatuAudit Environment Configuration

# GitHub OAuth Configuration (update these with your values)
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:8080/auth/github

# API Configuration
API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:8080

# Database Configuration
DATABASE_URL=sqlite:///./uatu_audit.db

# Security Configuration
SECRET_KEY=uatu-super-secret-key-change-this
JWT_SECRET_KEY=uatu-jwt-secret-key-change-this

# Application Configuration
DEBUG=true
ENVIRONMENT=development

# Port Configuration
DASHBOARD_PORT=8080
API_PORT=8000

# Audit Configuration
DEFAULT_AUDIT_PRICE_USDC=200
MAX_AUDIT_TIME_SECONDS=30
"""
            with open(env_file, 'w') as f:
                f.write(env_content)
            print("✅ Basic .env file created")
    else:
        print("✅ .env file already exists")
    
    return True

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating project directories...")
    
    directories = [
        'backend',
        'audit_outputs',
        'test_outputs', 
        'logs',
        'temp',
        'reports'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"   ✅ {directory}/")
    
    print("✅ All directories created!")

def test_system():
    """Test the system with mock audits"""
    print("\n🧪 Testing system with mock audits...")
    
    try:
        # Run the mock audit test
        result = subprocess.run([sys.executable, 'test_mock_audit.py'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Mock audit tests passed!")
            return True
        else:
            print("❌ Mock audit tests failed:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def create_startup_scripts():
    """Create convenient startup scripts"""
    print("\n🚀 Creating startup scripts...")
    
    # Create start script for Unix systems
    start_script = """#!/bin/bash
echo "🚀 Starting UatuAudit Platform"
echo "Backend API: http://localhost:8000"
echo "Frontend: http://localhost:8080"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

# Start backend in background
python3 run_backend.py &
BACKEND_PID=$!

# Start frontend (if Django server exists)
if [ -f "manage.py" ]; then
    python3 manage.py runserver 8080 &
    FRONTEND_PID=$!
fi

# Wait for Ctrl+C
trap "echo 'Stopping servers...'; kill $BACKEND_PID 2>/dev/null; kill $FRONTEND_PID 2>/dev/null; exit" INT

wait
"""
    
    with open('start.sh', 'w') as f:
        f.write(start_script)
    
    # Make executable
    os.chmod('start.sh', 0o755)
    print("   ✅ start.sh created")
    
    # Create Windows batch script
    batch_script = """@echo off
echo 🚀 Starting UatuAudit Platform
echo Backend API: http://localhost:8000
echo Frontend: http://localhost:8080
echo API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop

start /B python run_backend.py
if exist manage.py (
    start /B python manage.py runserver 8080
)

pause
"""
    
    with open('start.bat', 'w') as f:
        f.write(batch_script)
    print("   ✅ start.bat created")

def print_completion_message():
    """Print setup completion message"""
    print("""
🎉 UatuAudit Platform Setup Complete!
=====================================

📁 Project Structure:
   backend/           - FastAPI backend server
   examples/          - Sample Solidity contracts
   test_outputs/      - Generated audit reports
   audit_outputs/     - Live audit results

🚀 Quick Start:
   1. Update .env with your GitHub OAuth credentials
   2. Run: python3 run_backend.py
   3. Visit: http://localhost:8000/docs for API docs

🧪 Test Mock Audits:
   • python3 test_mock_audit.py
   • Check test_outputs/ for generated reports

📖 Features Ready:
   ✅ Base blockchain wallet connection
   ✅ GitHub OAuth integration
   ✅ Webhook support for repository updates
   ✅ Mock audit testing with existing .sol files
   ✅ PDF report generation
   ✅ Real-time audit progress tracking

🔧 Next Steps:
   1. Set up GitHub OAuth app and update GITHUB_CLIENT_ID
   2. Configure webhooks for repository monitoring
   3. Connect real audit tools (Slither, MythX, etc.)
   4. Deploy to production environment

Happy auditing! 🔒
""")

def main():
    """Main setup function"""
    print_banner()
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Setup environment
    if not setup_environment():
        print("❌ Failed to setup environment")
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Test system
    if not test_system():
        print("⚠️ System tests failed, but setup can continue")
    
    # Create startup scripts
    create_startup_scripts()
    
    # Print completion message
    print_completion_message()

if __name__ == "__main__":
    main()