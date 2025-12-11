# Streaming Agent Service API

## Overview

The agent service now supports **streaming responses** that yield action and observation events during the agent's execution loop, similar to OpenAI's streaming API.

## Streaming vs Non-Streaming

### Non-Streaming (Original)
```python
import requests

response = requests.post(
    "http://sf.lti.cs.cmu.edu:8001/sessions/{session_id}/prompt",
    json={"prompt": "Create a hello world script", "stream": False}
)
result = response.json()
print(result["response"])
```

### Streaming (New)
```python
import requests
import json

response = requests.post(
    "http://sf.lti.cs.cmu.edu:8001/sessions/{session_id}/prompt",
    json={"prompt": "Create a hello world script", "stream": True},
    stream=True
)

for line in response.iter_lines():
    if line and line.startswith(b'data: '):
        event = json.loads(line[6:])
        print(event)
```

## Event Types

The streaming API yields different event types during execution:

### 1. **thinking** - Agent is reasoning
```json
{
  "type": "thinking",
  "content": "Step 1: Agent is thinking..."
}
```

### 2. **action** - Agent is taking an action (calling a tool)
```json
{
  "type": "action",
  "action": "Using tool: bash",
  "tool": "bash",
  "arguments": {"command": "ls -la"},
  "reasoning": "I need to list the files..."
}
```

### 3. **observation** - Agent received result from tool
```json
{
  "type": "observation",
  "tool": "bash",
  "result": "total 8\ndrwxr-xr-x...",
  "success": true
}
```

### 4. **response** - Final response from agent
```json
{
  "type": "response",
  "content": "I've created the hello world script...",
  "finished": true
}
```

### 5. **error** - An error occurred
```json
{
  "type": "error",
  "error": "Error message here"
}
```

### 6. **done** - Stream completed
```json
{
  "type": "done"
}
```

## Python Client Example

```python
import requests
import json

def stream_agent(session_id, prompt):
    """Stream agent execution events."""
    url = f"http://sf.lti.cs.cmu.edu:8001/sessions/{session_id}/prompt"
    
    with requests.post(
        url,
        json={"prompt": prompt, "stream": True},
        stream=True
    ) as response:
        for line in response.iter_lines():
            if line and line.startswith(b'data: '):
                event = json.loads(line[6:])
                
                if event["type"] == "action":
                    print(f"🔧 {event['tool']}: {event['action']}")
                    
                elif event["type"] == "observation":
                    print(f"👁️  Result: {event['result'][:100]}...")
                    
                elif event["type"] == "response":
                    print(f"✅ {event['content']}")
                    
                elif event["type"] == "done":
                    break

# Usage
session = requests.post("http://sf.lti.cs.cmu.edu:8001/sessions").json()
stream_agent(session["session_id"], "Create a Python hello world script")
```

## JavaScript/TypeScript Example

```javascript
async function streamAgent(sessionId, prompt) {
    const response = await fetch(
        `http://sf.lti.cs.cmu.edu:8001/sessions/${sessionId}/prompt`,
        {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({prompt, stream: true})
        }
    );

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const event = JSON.parse(line.slice(6));
                
                if (event.type === 'action') {
                    console.log(`🔧 ${event.tool}: ${event.action}`);
                } else if (event.type === 'observation') {
                    console.log(`👁️  ${event.result}`);
                } else if (event.type === 'response') {
                    console.log(`✅ ${event.content}`);
                }
            }
        }
    }
}
```

## Agent Loop Flow

The streaming API exposes the agent's internal loop:

```
User Prompt
    ↓
[THINKING] Agent analyzes the task
    ↓
[ACTION] Agent decides to use a tool (e.g., "bash")
    ↓
[OBSERVATION] Tool executes and returns result
    ↓
[THINKING] Agent processes the result
    ↓
[ACTION] Agent uses another tool (e.g., "str_replace_based_edit_tool")
    ↓
[OBSERVATION] Tool executes and returns result
    ↓
... (loop continues) ...
    ↓
[RESPONSE] Agent provides final answer
    ↓
[DONE] Stream ends
```

## Benefits

1. **Real-time feedback**: See what the agent is doing as it works
2. **Better UX**: Show progress to users instead of waiting for completion
3. **Debugging**: Understand the agent's reasoning and tool usage
4. **Transparency**: Users can see each step of the agent's process
5. **Compatible**: Similar to OpenAI's streaming API pattern

## API Endpoint

**POST** `/sessions/{session_id}/prompt`

**Request Body:**
```json
{
  "prompt": "Your task here",
  "stream": true,  // Set to true for streaming
  "history": []    // Optional conversation history
}
```

**Response:**
- If `stream: false`: JSON response with `response` and `history`
- If `stream: true`: Server-Sent Events (SSE) stream with event chunks

## Testing

Run the test client:
```bash
python test_streaming_client.py
```

This will demonstrate both streaming and non-streaming modes.

## Notes

- Streaming uses Server-Sent Events (SSE) format
- Each event is prefixed with `data: ` followed by JSON
- Compatible with standard SSE clients
- Works with both Python `requests` and JavaScript `fetch`
- The agent loop continues until task completion or max steps reached
