#!/usr/bin/env python3
"""
Startup script for Wheel Strategy Dashboard with Background Delta Service
Runs both the IBKR delta service and the main Flask application
"""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path

def start_delta_service():
    """Start the background delta service"""
    print("🚀 Starting IBKR Delta Service...")

    # Ensure we run from the python/ directory so relative imports/files work
    python_dir = Path(__file__).resolve().parent

    # Start delta service in background
    delta_process = subprocess.Popen(
        [sys.executable, 'ibkr_delta_service.py'],
        cwd=str(python_dir),
        # Inherit stdout/stderr to avoid deadlocks from unread pipes.
    )
    
    print(f"✅ Delta service started with PID: {delta_process.pid}")
    return delta_process

def start_flask_app():
    """Start the main Flask application"""
    print("🚀 Starting Flask Dashboard...")

    python_dir = Path(__file__).resolve().parent

    # Start Flask app in background
    flask_process = subprocess.Popen(
        [sys.executable, 'complete-wheel-strategy-system.py'],
        cwd=str(python_dir),
        # Inherit stdout/stderr to avoid deadlocks from unread pipes.
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
    """Main function to start both services"""
    processes = {}
    delta_failed_logged = False
    
    try:
        # Start delta service first
        processes['delta_service'] = start_delta_service()
        
        # Wait a moment for delta service to initialize
        print("⏰ Waiting for delta service to initialize...")
        time.sleep(5)
        
        # Start Flask app
        processes['flask_app'] = start_flask_app()
        
        print("\n🎉 Both services started successfully!")
        print("📊 Dashboard available at: http://localhost:7002")
        print("📈 Delta service running in background")
        print("\nPress Ctrl+C to stop all services")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)

            # If the Flask app dies, stop everything.
            flask = processes.get('flask_app')
            if flask and flask.poll() is not None:
                print("❌ flask_app has stopped unexpectedly")
                return

            # If the delta service dies, keep the dashboard running (it will fall back to estimates).
            delta = processes.get('delta_service')
            if delta and delta.poll() is not None and not delta_failed_logged:
                delta_failed_logged = True
                print("⚠️  delta_service stopped (continuing without live greeks)")
                processes['delta_service'] = None
            
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cleanup(processes)

if __name__ == "__main__":
    main() 