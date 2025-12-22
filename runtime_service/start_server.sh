#!/bin/bash

# Navigate to the runtime_service directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the runtime service
echo "Starting Runtime Environment Service on port 8001..."
python main.py