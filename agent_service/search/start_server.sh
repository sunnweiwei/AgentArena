#!/bin/bash
# Start the Search Agent Server

cd "$(dirname "$0")"
echo "Starting Search Agent Server on port 8001..."
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload

