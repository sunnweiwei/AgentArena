# MCP (Model Context Protocol) Integration

## Overview

This document describes the MCP integration that allows users to add MCP servers (like filesystem MCP, search MCP) and have agents use their tools directly.

## Architecture

### Components

1. **Database Model** (`MCPServer` in `backend/main.py`)
   - Stores MCP server configurations per user
   - Fields: name, command, args, env, enabled

2. **MCP Manager** (`agent_service/mcp_manager.py`)
   - Manages connections to MCP servers
   - Provides tool discovery and execution
   - Converts MCP tools to function schema format

3. **Backend API** (`backend/main.py`)
   - `/api/mcp/servers` - CRUD operations for MCP servers
   - `/api/mcp/servers/{server_id}/tools` - Get tools from a server
   - Passes MCP server configs to agent server in requests

4. **Agent Integration** (`agent_service/search_agent.py`)
   - Loads MCP tools and includes them in tool description
   - Executes MCP tool calls in the agent loop
   - Returns results in the same format as regular tools

5. **Frontend UI** (to be implemented)
   - Configure MCP servers
   - View available tools
   - Enable/disable servers

## Data Flow

1. User configures MCP server in frontend
2. Frontend calls `/api/mcp/servers` to save configuration
3. When agent request is made, backend loads enabled MCP servers for user
4. Backend passes MCP server configs to agent server in request
5. Agent server connects to MCP servers and loads tools
6. Agent sees MCP tools alongside regular tools
7. When agent calls MCP tool, agent server executes it via MCP manager
8. Results are returned in `<|tool|>` format

## MCP Server Configuration

Example configuration:
```json
{
  "name": "Filesystem MCP",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
  "env": null
}
```

## Tool Format

MCP tools are converted to the same function schema format as regular tools:
```python
{
  "type": "function",
  "function": {
    "name": "mcp_tool_name",
    "description": "Tool description",
    "parameters": {
      "type": "object",
      "properties": {...},
      "required": [...]
    }
  }
}
```

## Implementation Status

- [x] Database model for MCP servers
- [x] MCP manager for connections and tool execution
- [x] Backend API endpoints
- [ ] Agent integration (loading MCP tools)
- [ ] Agent integration (executing MCP tools)
- [ ] Frontend UI for configuration
