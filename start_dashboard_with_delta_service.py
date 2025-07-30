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
    
    # Start delta service in background
    delta_process = subprocess.Popen([
        sys.executable, 'ibkr_delta_service.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    print(f"✅ Delta service started with PID: {delta_process.pid}")
    return delta_process

def start_flask_app():
    """Start the main Flask application"""
    print("🚀 Starting Flask Dashboard...")
    
    # Start Flask app in background
    flask_process = subprocess.Popen([
        sys.executable, 'complete-wheel-strategy-system.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
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
    
    try:
        # Start delta service first
        processes['delta_service'] = start_delta_service()
        
        # Wait a moment for delta service to initialize
        print("⏰ Waiting for delta service to initialize...")
        time.sleep(5)
        
        # Start Flask app
        processes['flask_app'] = start_flask_app()
        
        print("\n🎉 Both services started successfully!")
        print("📊 Dashboard available at: http://localhost:7001")
        print("📈 Delta service running in background")
        print("\nPress Ctrl+C to stop all services")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
            # Check if processes are still running
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