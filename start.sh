#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Start the Node.js server in the background
node server.js &

# Store the Node.js server's process ID
NODE_PID=$!

# Start the Python bot
python bot.py

# If the Python bot exits, stop the Node.js server
kill $NODE_PID
