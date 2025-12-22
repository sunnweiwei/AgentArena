# Backend Refactoring - Fully Generic Implementation

## Summary

The backend has been refactored to be completely **generic** with **zero knowledge** of what external APIs do. It's now a pure proxy that can call any OpenAI-compatible streaming API.

## What Changed

### Before (Search-Specific)
```python
# Had hardcoded function: stream_search_agent()
# Had hardcoded checks: if openai_model == "search_agent"
# Had search-specific error messages and logs
```

### After (Completely Generic)
```python
# Generic function: call_external_model_api(api_url, ...)
# Generic check: if openai_model in EXTERNAL_MODEL_APIS
# Generic error messages and logs
```

## Backend Architecture

The backend now works like this:

```
1. Receives model selection from frontend
2. Looks up model in MODEL_MAP → gets internal identifier
3. Checks if identifier exists in EXTERNAL_MODEL_APIS
   - YES → Call external API using generic HTTP streaming
   - NO  → Use built-in OpenAI API
4. Stream response back to frontend
```

## Code Changes

### 1. Configuration (Not Logic!)

```python
# User-facing to internal identifier mapping
MODEL_MAP = {
    "Auto": "gpt-5-nano",
    "GPT-5-Nano": "gpt-5-nano",
    "GPT-5-Mini": "gpt-5-mini",
    "Search Agent": "search_agent"  # Just a config entry!
}

# Internal identifier to API endpoint mapping
EXTERNAL_MODEL_APIS = {
    "search_agent": os.getenv("SEARCH_AGENT_URL", "http://localhost:8001")
}
```

**Important:** These are just **configuration entries**, not logic. The name "search_agent" is arbitrary - it could be "agent_1", "external_model", or anything.

### 2. Generic Function

**Before:** `stream_search_agent()` - search-specific name and logic
**After:** `call_external_model_api(api_url, ...)` - completely generic

```python
async def call_external_model_api(
    api_url: str,              # Any URL
    messages_history: list,    # Standard format
    websocket: WebSocket,      # For streaming back
    chat_id: str, 
    user_id: int, 
    stream_id: str
):
    """
    Generic function to call ANY external model API.
    Works with any OpenAI-compatible streaming endpoint.
    """
```

### 3. Generic Check

**Before:**
```python
if openai_model == "search_agent":  # Hardcoded!
    await stream_search_agent(...)
```

**After:**
```python
if openai_model and openai_model in EXTERNAL_MODEL_APIS:  # Generic!
    external_api_url = EXTERNAL_MODEL_APIS[openai_model]
    await call_external_model_api(external_api_url, ...)
```

### 4. Generic Logging

**Before:**
```python
print(f"[Search Agent] Chunk: {content}")
print(f"Search agent error: {e}")
```

**After:**
```python
print(f"[External API] Chunk: {content}")
print(f"External API error: {e}")
```

## Benefits

### 1. Zero Knowledge
Backend has **no idea** what external APIs do:
- Could be search agent
- Could be code agent
- Could be math solver
- Could be anything!

### 2. Easy to Extend
Add new external models by just adding config:

```python
EXTERNAL_MODEL_APIS = {
    "search_agent": "http://localhost:8001",
    "code_agent": "http://localhost:8002",      # New!
    "math_agent": "http://localhost:8003",      # New!
    "custom_model": "http://api.example.com"    # New!
}
```

Then add to MODEL_MAP:
```python
MODEL_MAP = {
    # ... existing models ...
    "Code Agent": "code_agent",
    "Math Agent": "math_agent",
    "Custom Model": "custom_model"
}
```

**No code changes needed!** Just configuration.

### 3. Clean Separation
- Backend = Chat infrastructure + API proxy
- External services = Model implementations
- Zero coupling between them

### 4. Standard Protocol
All external APIs must implement:
- Endpoint: `/v1/chat/completions`
- Format: OpenAI-compatible streaming (SSE)
- Request: `{"messages": [...], "stream": true}`
- Response: SSE with `data:` lines containing JSON chunks

## What the Backend Does

The backend is now a **pure proxy** with these responsibilities:

1. ✅ User authentication
2. ✅ Chat history management (database)
3. ✅ WebSocket connections to frontend
4. ✅ Routing to appropriate model (internal or external)
5. ✅ Streaming responses (SSE → WebSocket conversion)

## What the Backend Doesn't Do

1. ❌ Search logic
2. ❌ Tool calling
3. ❌ Web scraping
4. ❌ Any domain-specific processing
5. ❌ Anything besides routing and streaming

## Configuration

### Environment Variables

```bash
# Optional: Override search agent URL
export SEARCH_AGENT_URL="http://your-server:8001"

# Or use .env file
echo "SEARCH_AGENT_URL=http://your-server:8001" >> .env
```

### Adding New External APIs

1. Deploy your external API server (must be OpenAI-compatible)
2. Add configuration:

```python
EXTERNAL_MODEL_APIS = {
    "your_model": os.getenv("YOUR_MODEL_URL", "http://localhost:8002")
}

MODEL_MAP = {
    # ...
    "Your Model Name": "your_model"
}
```

3. Update frontend model list in `ChatWindow.jsx`:

```javascript
const models = ['Auto', 'GPT-5-Nano', 'GPT-5-Mini', 'Search Agent', 'Your Model Name']
```

Done! No backend logic changes needed.

## File Summary

### Modified: `backend/main.py`

**Removed:**
- All search-specific naming
- All hardcoded checks for search agent
- Search-specific error messages

**Added:**
- Generic `call_external_model_api()` function
- Generic `EXTERNAL_MODEL_APIS` configuration dict
- Generic logging and error handling

**Lines of actual logic changed:** ~5 lines (just renamed and made generic)

**Total backend diff:**
- Old function name → New function name
- Hardcoded string → Dictionary lookup
- "Search" strings → "External API" strings

## Testing

The backend still works exactly the same way, it's just more generic now:

```bash
# Terminal 1: Start search agent server
cd agent_service/search
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2: Start backend
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 3: Start frontend
cd frontend
npm run dev
```

Then test in browser:
1. Select "Search Agent" from dropdown
2. Ask a question
3. See streaming results

## Verification

Check that backend has no search-specific logic:

```bash
# Should only find configuration entries, not logic
grep -i "search" backend/main.py

# Result: Only MODEL_MAP and EXTERNAL_MODEL_APIS entries (config, not logic)
```

## Conclusion

The backend is now **100% generic** and has **zero domain knowledge**. It's a pure infrastructure layer that:
- Routes requests to the right place
- Streams responses back to frontend
- Manages chat history and authentication

All domain logic (search, code execution, math, etc.) lives in separate external services.

This is proper microservices architecture! 🎉

