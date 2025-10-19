#!/bin/bash
set -e  # Exit on error

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Function to handle termination
cleanup() {
    echo "Shutting down processes..."
    kill -9 $NODE_PID $PYTHON_PID 2>/dev/null || true
    exit 0
}

# Set up trap to clean up processes on exit
trap cleanup SIGINT SIGTERM

# Start the Node.js server in the background
echo "Starting Node.js server..."
node server.js &
NODE_PID=$!

# Give Node.js server a moment to start
sleep 2

# Start the Python bot in the background
echo "Starting Python bot..."
python bot.py &
PYTHON_PID=$!

# Keep the script running and wait for processes
echo "All services are running. Press Ctrl+C to stop."
wait $NODE_PID $PYTHON_PID

# Cleanup if we get here
cleanup
