"""
Minimal test script for agent service streaming API.
Similar to OpenAI's streaming API pattern.
"""

import requests
import json

# Service URL
BASE_URL = "http://sf.lti.cs.cmu.edu:8001"

# 1. Create session
print("Creating session...")
response = requests.post(f"{BASE_URL}/sessions")
session = response.json()
session_id = session["session_id"]
print(f"Session ID: {session_id}\n")

# 2. Stream a task (similar to OpenAI's streaming API)
print("Streaming task...\n")
print("=" * 60)

response = requests.post(
    f"{BASE_URL}/sessions/{session_id}/prompt",
    json={
        "prompt": "Create a simple HTML file introducing Elon Musk",
        "stream": True
    },
    stream=True
)

# Print each event as it arrives
for line in response.iter_lines():
    if line and line.startswith(b'data: '):
        event = json.loads(line[6:])
        print(event)
        print()  # Empty line for readability
