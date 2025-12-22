# Search Agent Integration - Changes Summary

## Overview

The search agent has been integrated as a **separate microservice** that the chat backend calls via HTTP API. This keeps the backend clean and separates concerns.

## New Files Created

### 1. `agent_service/search/server.py` (NEW)
- Standalone FastAPI server for search agent
- Provides OpenAI-compatible streaming API
- Handles web search via Tavily API
- Runs on port 8001

### 2. `agent_service/search/requirements.txt` (NEW)
- Dependencies for search agent server
- Includes: fastapi, uvicorn, openai, tavily-python, pydantic

### 3. `agent_service/search/start_server.sh` (NEW)
- Convenience script to start search agent server
- Usage: `./start_server.sh`

### 4. `SEARCH_AGENT_SETUP.md` (NEW)
- Complete documentation for search agent
- Architecture diagram
- Setup instructions
- API reference
- Troubleshooting guide

### 5. `start_all.sh` (NEW)
- Script to start all services (search agent, backend, frontend)
- Opens each in a separate terminal window (macOS)
- Usage: `./start_all.sh`

### 6. `SEARCH_AGENT_CHANGES.md` (THIS FILE)
- Summary of all changes made

## Modified Files

### 1. `backend/main.py`
**Changes:**
- Added `aiohttp` and `json` imports
- Removed all search agent implementation code (agent_loop, Tavily imports, etc.)
- Added `SEARCH_AGENT_URL` configuration (defaults to http://localhost:8001)
- Added "Search Agent" to MODEL_MAP
- Modified `stream_search_agent()` to call search agent server API via HTTP
- Uses aiohttp for async HTTP streaming

**Removed:**
- All Tavily-related code
- agent_loop function (moved to server.py)
- search_tool imports
- TAVILY_API_KEY configuration

**Net effect:** Backend is now ~150 lines shorter and has no search-specific logic

### 2. `backend/requirements.txt`
**Changes:**
- Removed: `tavily-python>=0.5.0`
- Added: `aiohttp>=3.9.0` (for HTTP client)

### 3. `frontend/src/components/ChatWindow.jsx`
**Changes:**
- Added "Search Agent" to models array
- No other changes needed (uses same WebSocket protocol)

## Architecture

### Before (Monolithic)
```
Frontend ◄──WS──► Backend (includes search agent logic)
                     └──► Tavily API
```

### After (Microservices)
```
Frontend ◄──WS──► Backend ◄──HTTP──► Search Agent Server
                                          └──► Tavily API
```

## Benefits of New Architecture

1. **Separation of Concerns**
   - Backend focuses on chat, auth, database
   - Search agent handles search logic independently

2. **Clean Code**
   - Backend has no search-related dependencies
   - Search agent is isolated and testable

3. **Scalability**
   - Can run multiple search agent instances
   - Can deploy search agent separately

4. **Reusability**
   - Search agent server can be used by other apps
   - Provides standard OpenAI-compatible API

5. **Development**
   - Update search agent without touching backend
   - Easier to add new tools and features

6. **Deployment**
   - Services can be deployed independently
   - Better resource allocation

## How to Run

### Option 1: Use start_all.sh (Recommended for macOS)
```bash
./start_all.sh
```

### Option 2: Manual startup (Works on all platforms)

**Terminal 1 - Search Agent Server:**
```bash
cd agent_service/search
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2 - Backend:**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

## Testing

1. Open http://localhost:3000
2. Log in with any username
3. Select "Search Agent" from model dropdown
4. Ask: "What's the latest news about artificial intelligence?"
5. Observe:
   - Reasoning blocks (`<think>` tags)
   - Search queries being executed
   - Content extraction from web pages
   - Final answer based on search results

## API Communication Flow

```
User Types Message
      ↓
Frontend (WebSocket) → Backend
      ↓
Backend detects "Search Agent" model
      ↓
Backend HTTP POST → Search Agent Server (/v1/chat/completions)
      ↓
Search Agent:
  1. Analyzes query
  2. Decides to use search tool
  3. Calls Tavily API
  4. Processes results
  5. Generates response
      ↓
Search Agent streams chunks (SSE) → Backend
      ↓
Backend forwards chunks (WebSocket) → Frontend
      ↓
User sees streaming response
```

## Configuration

### Backend (.env or environment)
```bash
SEARCH_AGENT_URL=http://localhost:8001  # Default
```

### Search Agent Server (API keys)
```bash
# Option 1: Files (recommended)
echo "your-openai-key" > openaikey
echo "your-tavily-key" > tavilykey

# Option 2: Environment variables
export OPENAI_API_KEY="your-openai-key"
export TAVILY_API_KEY="your-tavily-key"
```

## Dependencies

### Backend
- aiohttp>=3.9.0 (new dependency for HTTP client)
- Removed: tavily-python

### Search Agent Server
- fastapi>=0.104.1
- uvicorn[standard]>=0.24.0
- openai>=2.8.0
- tavily-python>=0.5.0
- pydantic>=2.0.0

## Troubleshooting

### "Connection refused" error
- Ensure search agent server is running on port 8001
- Check `SEARCH_AGENT_URL` in backend configuration

### Search agent not responding
- Check search agent server logs
- Verify API keys are configured correctly
- Test health endpoint: http://localhost:8001/health

### Backend can't find search agent
- Start search agent server BEFORE backend
- Check if port 8001 is available
- Try: `curl http://localhost:8001/health`

## Next Steps

### Potential Enhancements

1. **Load Balancing**
   - Run multiple search agent instances
   - Add load balancer in front

2. **Caching**
   - Cache search results
   - Reduce API calls

3. **More Tools**
   - Add calculator tool
   - Add code execution tool
   - Add database query tool

4. **Authentication**
   - Add API key auth between backend and search agent
   - Secure the search agent endpoint

5. **Monitoring**
   - Add metrics (response time, token usage)
   - Add logging/tracing
   - Add error alerting

6. **Docker**
   - Create Dockerfile for each service
   - Add docker-compose.yml

## Files Summary

**New files: 6**
- agent_service/search/server.py
- agent_service/search/requirements.txt
- agent_service/search/start_server.sh
- SEARCH_AGENT_SETUP.md
- start_all.sh
- SEARCH_AGENT_CHANGES.md

**Modified files: 3**
- backend/main.py (simplified, -150 lines)
- backend/requirements.txt (swapped tavily for aiohttp)
- frontend/src/components/ChatWindow.jsx (added model option)

**Total lines of code:**
- Search agent server: ~280 lines
- Backend changes: -150 lines (net reduction)
- Total new code: ~130 lines

