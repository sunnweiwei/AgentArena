# 🚀 Agent Service - Quick Reference

## Service Info
- **URL**: `http://sf.lti.cs.cmu.edu:8001`
- **Status**: ✅ RUNNING
- **Features**: Streaming + Non-streaming

## API Endpoints

### 1. Health Check
```bash
curl http://sf.lti.cs.cmu.edu:8001/health
```

### 2. Create Session
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions
```

### 3. Prompt (Non-Streaming)
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions/{SESSION_ID}/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your task", "stream": false}'
```

### 4. Prompt (Streaming) ⭐
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions/{SESSION_ID}/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Your task", "stream": true}'
```

## Event Types (Streaming)

| Type | Description |
|------|-------------|
| `thinking` | Agent is reasoning |
| `action` | Agent calls a tool |
| `observation` | Tool result |
| `response` | Final answer |
| `error` | Error occurred |
| `done` | Stream complete |

## Python Client

```python
import requests
import json

# Create session
session = requests.post("http://sf.lti.cs.cmu.edu:8001/sessions").json()
sid = session["session_id"]

# Stream
with requests.post(
    f"http://sf.lti.cs.cmu.edu:8001/sessions/{sid}/prompt",
    json={"prompt": "Create hello.py", "stream": True},
    stream=True
) as r:
    for line in r.iter_lines():
        if line.startswith(b'data: '):
            event = json.loads(line[6:])
            print(event)
```

## JavaScript Client

```javascript
const response = await fetch(url, {
    method: 'POST',
    body: JSON.stringify({prompt: task, stream: true})
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) {
            const event = JSON.parse(line.slice(6));
            console.log(event);
        }
    }
}
```

## Test

```bash
python test_streaming_client.py
```

## Docs

- `STREAMING_COMPLETE.md` - Full guide
- `STREAMING_API.md` - API reference
- `CONTRIBUTING.md` - Development guide
