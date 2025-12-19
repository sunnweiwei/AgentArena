# Search Agent Setup Documentation

## Overview

The Search Agent is a specialized AI model that can perform web searches and extract information from web pages to answer questions. It uses:
- **OpenAI GPT-5-mini** for reasoning and response generation
- **Tavily API** for web search and content extraction

## Architecture

```
Frontend (React)
    ↓ (WebSocket + HTTPS)
Backend (FastAPI - Port 8000)
    ↓ (HTTP API call)
Search Agent Server (FastAPI - Port 8001)
    ↓ (API calls)
OpenAI API + Tavily API
```

## Components

### 1. Search Agent Server (`agent_service/search/server.py`)
- **Port:** 8001
- **Framework:** FastAPI with uvicorn
- **Endpoints:**
  - `POST /v1/chat/completions` - OpenAI-compatible streaming chat endpoint
  - `GET /health` - Health check (returns OpenAI and Tavily availability)
  - `GET /` - Server info

### 2. Backend Integration (`backend/main.py`)
- **Model Mapping:** "Search Agent" → "search_agent"
- **External API Config:** Points to `http://localhost:8001`
- **Routing Logic:** Detects external models and routes to appropriate API

### 3. Frontend Integration (`frontend/src/components/ChatWindow.jsx`)
- **Model Selector:** Includes "Search Agent" in the dropdown
- **No Special Handling:** Works like any other model from the UI perspective

## File Structure

```
agent_service/
├── search/
│   ├── server.py              # Main FastAPI server
│   ├── test.py                # Tool definitions and utility functions
│   ├── requirements.txt       # Python dependencies
│   └── start_server.sh        # Server startup script
└── tools/
    └── tool_prompt.py         # Tool description formatting utilities
```

## Setup Instructions

### Prerequisites

1. **Python Dependencies** (installed on server):
   ```bash
   fastapi>=0.104.1
   uvicorn[standard]>=0.24.0
   openai>=2.8.0
   tavily-python>=0.5.0
   pydantic>=2.0.0
   ```

2. **API Keys:**
   - OpenAI API key at `/usr1/data/weiweis/chat_server/openaikey`
   - Tavily API key: Uses default dev key or can be set via `TAVILY_API_KEY` env var

3. **Python Path:**
   - Must include `/usr1/data/weiweis/chat_server` for module imports

### Starting the Server

**Option 1: Using the startup script**
```bash
./start_search_agent.sh
```

**Option 2: Manual start**
```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "cd /usr1/data/weiweis/chat_server/agent_service/search && export PYTHONPATH=/usr1/data/weiweis/chat_server:\$PYTHONPATH && nohup /home/weiweis/.local/bin/uvicorn server:app --host 0.0.0.0 --port 8001 > /usr1/data/weiweis/chat_server/logs/search_agent.log 2>&1 &"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Verifying the Setup

1. **Check Search Agent Health:**
   ```bash
   curl -s http://sf.lti.cs.cmu.edu:8001/health | jq .
   ```
   Expected output:
   ```json
   {
     "status": "healthy",
     "openai_available": true,
     "tavily_available": true
   }
   ```

2. **Test the API:**
   ```bash
   curl -X POST http://sf.lti.cs.cmu.edu:8001/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "messages": [{"role": "user", "content": "What is the weather in Tokyo?"}],
       "stream": true
     }'
   ```

3. **Check Logs:**
   ```bash
   ssh weiweis@sf.lti.cs.cmu.edu "tail -f /usr1/data/weiweis/chat_server/logs/search_agent.log"
   ```

4. **Test via Chat Interface:**
   - Open https://sf.lti.cs.cmu.edu:3000/
   - Click on the model selector (shows "Auto" by default)
   - Select "Search Agent"
   - Send a message that requires web search (e.g., "What's the latest news about AI?")
   - The agent should search the web and provide informed answers

## How It Works

### Agent Loop

The search agent uses an iterative loop:

1. **User sends a message** → Agent receives it with conversation history
2. **Agent reasons** → Uses GPT-5-mini with reasoning capabilities
3. **Agent decides to use tools** → Can call `search()` or `extract()` functions
4. **Execute tool calls** → Tavily API performs web search or content extraction
5. **Agent receives results** → Gets search results or page content
6. **Steps 2-5 repeat** → Until agent has enough information
7. **Agent responds** → Streams final answer back to user

### Tool Functions

**`search(query: str, max_results: int = 5)`**
- Performs web search using Tavily
- Returns titles, URLs, and content snippets

**`extract(url: str, query: str = None)`**
- Extracts full content from a webpage
- Optional query parameter for focused extraction
- Content is truncated to ~4000 words

### Streaming Format

The server uses OpenAI-compatible Server-Sent Events (SSE) format:

```
data: {"choices": [{"delta": {"content": "..."}, "index": 0, "finish_reason": null}]}

data: {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]}

data: [DONE]
```

This allows seamless integration with the existing backend streaming infrastructure.

## Troubleshooting

### Server Won't Start

**Check if port 8001 is already in use:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "ps aux | grep 'uvicorn.*8001'"
```

**Kill existing process:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "pkill -f 'uvicorn.*8001'"
```

**Check logs for errors:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "tail -100 /usr1/data/weiweis/chat_server/logs/search_agent.log"
```

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'agent_service'`

**Solution:** Ensure `PYTHONPATH` includes the server root:
```bash
export PYTHONPATH=/usr1/data/weiweis/chat_server:$PYTHONPATH
```

### API Not Responding

**Check if service is running:**
```bash
curl http://sf.lti.cs.cmu.edu:8001/health
```

**Check backend can reach it:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "curl -s http://localhost:8001/health"
```

### Search Not Working

**Check Tavily API key:**
- Server logs show "Tavily API key loaded: tvly-dev-F..."
- If using default dev key, it has rate limits

**Check OpenAI API:**
- Server logs show "OpenAI client initialized successfully"
- Verify API key exists at `/usr1/data/weiweis/chat_server/openaikey`

## Maintenance

### Updating Code

1. **Sync changes:**
   ```bash
   scp -r agent_service/search weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/agent_service/
   ```

2. **Restart server:**
   ```bash
   ssh weiweis@sf.lti.cs.cmu.edu "pkill -f 'uvicorn.*8001' && cd /usr1/data/weiweis/chat_server/agent_service/search && export PYTHONPATH=/usr1/data/weiweis/chat_server:\$PYTHONPATH && nohup /home/weiweis/.local/bin/uvicorn server:app --host 0.0.0.0 --port 8001 > /usr1/data/weiweis/chat_server/logs/search_agent.log 2>&1 &"
   ```

### Monitoring

**Watch logs in real-time:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "tail -f /usr1/data/weiweis/chat_server/logs/search_agent.log"
```

**Check resource usage:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu "ps aux | grep uvicorn"
```

## Future Enhancements

- [ ] Add more search tools (e.g., image search, news search)
- [ ] Implement caching for repeated queries
- [ ] Add authentication/rate limiting
- [ ] Support multiple concurrent requests better
- [ ] Add metrics and monitoring dashboard
- [ ] Integrate with more search providers

## References

- Backend integration: `backend/main.py` lines 95-101, 805-838
- Frontend model list: `frontend/src/components/ChatWindow.jsx` line 771
- Tool definitions: `agent_service/tools/tool_prompt.py` lines 204-278
- Search logic: `agent_service/search/test.py`

---

**Last Updated:** Dec 18, 2025
**Status:** ✅ Running on sf.lti.cs.cmu.edu:8001

