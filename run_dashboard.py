#!/usr/bin/env python3
"""
UatuAudit Dashboard Server Launcher
Starts the dashboard with wallet authentication
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 Starting UatuAudit Dashboard")
    print("=" * 40)
    
    # Set environment variables if not already set
    env = os.environ.copy()
    env.setdefault('PYTHONPATH', str(Path.cwd()))
    env.setdefault('HOST', '0.0.0.0')
    env.setdefault('PORT', '8080')
    
    print(f"📡 Dashboard will be available at: http://localhost:{env['PORT']}")
    print(f"🔧 Press Ctrl+C to stop the server")
    print("-" * 40)
    
    try:
        # Run the dashboard server
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "auditor.dashboard.server:app",
            "--host", env['HOST'],
            "--port", env['PORT'],
            "--reload"
        ], env=env)
        
    except KeyboardInterrupt:
        print("\n👋 Dashboard server stopped")
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()