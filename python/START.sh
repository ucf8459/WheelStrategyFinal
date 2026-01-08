#!/bin/bash
# =============================================================
# Wheel Strategy Dashboard - Quick Start
# =============================================================
# 
# BEFORE RUNNING:
# 1. Open TWS (Trader Workstation) and log in
# 2. Enable API access: Configure > API > Enable ActiveX and Socket Clients
# 3. Ensure port 7496 is set (Configure > API > Socket Port)
# 4. Add 127.0.0.1 to trusted IPs
#
# =============================================================

cd "$(dirname "$0")"

echo "🎯 Wheel Strategy Dashboard"
echo "============================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if TWS is running (port 7496)
if ! nc -z localhost 7496 2>/dev/null; then
    echo "⚠️  WARNING: TWS not detected on port 7496"
    echo "   Make sure Trader Workstation is running and API is enabled"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "🚀 Starting dashboard on http://localhost:7002"
echo "   Press Ctrl+C to stop"
echo ""

python complete-wheel-strategy-system.py

