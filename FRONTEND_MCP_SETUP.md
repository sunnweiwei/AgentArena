# Frontend MCP Setup - Zero Configuration

## How It Works

1. **Configure MCP in Frontend**: Go to Settings → MCP, add your MCP server configuration
2. **Check "Run on local machine"**: This tells the system the MCP server runs on your local machine
3. **Frontend Auto-Connects**: The frontend automatically connects to your local MCP servers
4. **Agent Calls Tools**: When the agent needs to call an MCP tool, it sends a request to the backend
5. **Backend Forwards to Frontend**: Backend forwards the request to your frontend via WebSocket
6. **Frontend Executes Locally**: Frontend executes the tool on your local machine and returns the result
7. **Result Returns to Agent**: Result flows back through backend to agent

## Setup Steps

### 1. Install Node.js MCP Bridge (One-time setup)

The frontend uses a lightweight Node.js server that auto-starts. You need Node.js installed.

### 2. Configure MCP Server

1. Open Settings in the frontend
2. Go to MCP section
3. Click "+ Add"
4. Fill in:
   - **Name**: e.g., "Local Filesystem MCP"
   - **Command**: `npx`
   - **Arguments** (one per line):
     ```
     -y
     @modelcontextprotocol/server-filesystem
     /Users/sunweiwei/NLP/base_project
     ```
   - **Check "Run on local machine"**: This is the key setting!

5. Click "Add Server"

### 3. That's It!

The frontend will automatically:
- Connect to your local MCP servers
- Handle tool calls when the agent needs them
- Execute tools locally and return results

## How It Works Technically

1. **Frontend MCP Executor** (`frontend/src/utils/mcpExecutor.js`):
   - Connects to local MCP servers via a Node.js bridge
   - Executes tools when requested by the agent

2. **Node.js Bridge** (`frontend_mcp_bridge/index.js`):
   - Lightweight server that runs MCP servers locally
   - Can be started via `npx` (no installation needed)

3. **Backend Proxy** (`backend/main.py`):
   - Receives tool call requests from agent service
   - Forwards to frontend via WebSocket
   - Waits for result and returns to agent

4. **Agent Service** (`agent_service/mcp_manager.py`):
   - Detects `bridge_url="local"` 
   - Sends HTTP request to backend instead of calling directly
   - Receives result and continues

## No Python Server Needed!

Unlike the previous approach, you don't need to run a separate Python server. The Node.js bridge can be started automatically by the frontend when needed, or you can run it once and it stays running.

## Auto-Start (Optional)

You can set up the Node.js bridge to auto-start on login. See `frontend_mcp_bridge/README.md` for instructions.

