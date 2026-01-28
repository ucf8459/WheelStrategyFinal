#!/usr/bin/env python3
"""
Startup script for Wheel Strategy Dashboard ONLY
Runs only the main Flask application without the delta service
"""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path

def start_flask_app():
    """Start the main Flask application"""
    print("🚀 Starting Flask Dashboard...")

    # Ensure we run from the python/ directory so relative imports/files work
    python_dir = Path(__file__).resolve().parent

    # Start Flask app in background
    flask_process = subprocess.Popen(
        [sys.executable, 'complete-wheel-strategy-system.py'],
        cwd=str(python_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    print(f"✅ Flask app started with PID: {flask_process.pid}")
    return flask_process

def cleanup(processes):
    """Clean up processes on exit"""
    print("\n🛑 Shutting down services...")
    for name, process in processes.items():
        if process and process.poll() is None:
            print(f"🛑 Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    print("✅ All services stopped")

def main():
    """Main function to start the dashboard"""
    processes = {}
    
    try:
        # Start Flask app only
        processes['flask_app'] = start_flask_app()
        
        print("\n🎉 Dashboard started successfully!")
        print("📊 Dashboard available at: http://localhost:7002")
        print("⚠️ Delta service NOT running - delta values will be estimates")
        print("\nPress Ctrl+C to stop the dashboard")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
            # Check if process is still running
            for name, process in processes.items():
                if process.poll() is not None:
                    print(f"❌ {name} has stopped unexpectedly")
                    return
            
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main()