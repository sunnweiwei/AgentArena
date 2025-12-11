"""
Example client for testing the streaming agent service.
Compatible with OpenAI-style streaming API.
"""

import requests
import json

# Server URL
BASE_URL = "http://sf.lti.cs.cmu.edu:8001"

def create_session():
    """Create a new agent session."""
    response = requests.post(f"{BASE_URL}/sessions")
    response.raise_for_status()
    return response.json()

def stream_prompt(session_id: str, prompt: str):
    """
    Send a prompt and stream the agent's action/observation loop.
    Similar to OpenAI's streaming API.
    """
    url = f"{BASE_URL}/sessions/{session_id}/prompt"
    data = {
        "prompt": prompt,
        "stream": True
    }
    
    # Stream the response
    with requests.post(url, json=data, stream=True) as response:
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                # Decode SSE format
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    try:
                        event = json.loads(data_str)
                        yield event
                    except json.JSONDecodeError:
                        continue

def non_stream_prompt(session_id: str, prompt: str):
    """Send a prompt without streaming (original behavior)."""
    url = f"{BASE_URL}/sessions/{session_id}/prompt"
    data = {
        "prompt": prompt,
        "stream": False
    }
    
    response = requests.post(url, json=data)
    response.raise_for_status()
    return response.json()

# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("Agent Service Streaming Test")
    print("=" * 60)
    
    # Create session
    print("\n1. Creating session...")
    session = create_session()
    session_id = session["session_id"]
    print(f"   Session ID: {session_id}")
    print(f"   Workspace: {session['workspace_path']}")
    
    # Test streaming
    print("\n2. Testing streaming API...")
    print("-" * 60)
    
    prompt = "Create a Python script that prints 'Hello, World!' and save it as hello.py"
    
    for event in stream_prompt(session_id, prompt):
        event_type = event.get("type")
        
        if event_type == "thinking":
            print(f"💭 {event.get('content')}")
            
        elif event_type == "action":
            print(f"\n🔧 ACTION: {event.get('action')}")
            print(f"   Tool: {event.get('tool')}")
            if event.get('reasoning'):
                print(f"   Reasoning: {event.get('reasoning')}")
            print(f"   Arguments: {json.dumps(event.get('arguments', {}), indent=2)}")
            
        elif event_type == "observation":
            print(f"\n👁️  OBSERVATION:")
            print(f"   Tool: {event.get('tool')}")
            print(f"   Success: {event.get('success')}")
            result = event.get('result', '')
            if len(result) > 200:
                print(f"   Result: {result[:200]}...")
            else:
                print(f"   Result: {result}")
            
        elif event_type == "response":
            print(f"\n✅ FINAL RESPONSE:")
            print(f"   {event.get('content')}")
            
        elif event_type == "error":
            print(f"\n❌ ERROR: {event.get('error')}")
            
        elif event_type == "done":
            print("\n" + "=" * 60)
            print("Stream completed")
            print("=" * 60)
    
    # Test non-streaming for comparison
    print("\n\n3. Testing non-streaming API (for comparison)...")
    print("-" * 60)
    
    prompt2 = "List the files in the current directory"
    result = non_stream_prompt(session_id, prompt2)
    print(f"Response: {result['response']}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
