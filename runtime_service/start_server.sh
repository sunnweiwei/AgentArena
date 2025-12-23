#!/bin/bash

# Navigate to the runtime_service directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load OPENAI_API_KEY from openaikey file if it exists
if [ -f "../openaikey" ]; then
    export OPENAI_API_KEY=$(cat ../openaikey)
elif [ -f "/usr1/data/weiweis/chat_server/openaikey" ]; then
    export OPENAI_API_KEY=$(cat /usr1/data/weiweis/chat_server/openaikey)
fi

# Start the runtime service
echo "Starting Runtime Environment Service on port 8005..."
python runtime_server.py