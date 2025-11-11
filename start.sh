#!/bin/bash

# Temporal Minesweeper Startup Script

echo "🚩 Starting Temporal Minesweeper..."
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start the worker in the background
echo "Starting Temporal worker..."
python -m src.worker &
WORKER_PID=$!
echo "✓ Worker started (PID: $WORKER_PID)"
echo ""

# Wait a moment for worker to initialize
sleep 2

# Start the Flask server
echo "Starting Flask server..."
echo ""
python -m src.server &
SERVER_PID=$!

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $WORKER_PID 2>/dev/null
    kill $SERVER_PID 2>/dev/null
    echo "✓ Shutdown complete"
    exit 0
}

# Trap SIGINT (Ctrl+C) and cleanup
trap cleanup SIGINT

echo "🎮 Minesweeper is running!"
echo "   Web UI: http://localhost:3000"
echo "   Temporal UI: http://localhost:8233"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Wait for processes
wait
