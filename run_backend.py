#!/usr/bin/env python3
"""
UatuAudit Backend Launcher
Starts the FastAPI backend server
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required packages are installed"""
    # Map distribution/package names to import module names
    required_imports = {
        'fastapi': 'fastapi',
        'uvicorn': 'uvicorn',
        'httpx': 'httpx',
        'python-jose': 'jose',
        'python-multipart': 'multipart',
        'SQLAlchemy': 'sqlalchemy',
        'python-dotenv': 'dotenv',
        'GitPython': 'git',
        'pydantic': 'pydantic',
        'cryptography': 'cryptography',
    }

    missing_packages = []

    for dist_name, import_name in required_imports.items():
        try:
            __import__(import_name)
        except ImportError:
            missing_packages.append(dist_name)

    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
        print("\n   OR install all at once:")
        print("   pip install -r backend/requirements.txt")
        return False

    return True

def setup_environment():
    """Setup environment variables"""
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        print("📄 Creating .env file from .env.example...")
        with open(env_example) as f:
            content = f.read()
        
        with open(env_file, 'w') as f:
            f.write(content)
        
        print("✅ .env file created!")
        print("⚠️  Please update .env with your actual configuration values")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    dirs = ['audit_outputs', 'logs', 'temp']
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)

def main():
    print("🚀 UatuAudit Backend Launcher")
    print("=" * 40)
    
    # Check requirements
    print("🔍 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    # Setup environment
    print("⚙️  Setting up environment...")
    if not setup_environment():
        print("Please configure your .env file and run again.")
        sys.exit(1)
    
    # Create directories
    print("📁 Creating directories...")
    create_directories()
    
    # Start the server
    print("🌟 Starting UatuAudit API server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    print("🔧 Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Change to backend directory and run the server
        backend_path = Path("backend")
        if backend_path.exists():
            os.chdir(backend_path)
        
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ])
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()