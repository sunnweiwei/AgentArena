"""
MCP (Model Context Protocol) Manager
Handles connections to MCP servers and tool execution
"""

import json
import subprocess
import asyncio
from typing import Dict, List, Optional, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPServerManager:
    """Manages connections to MCP servers and provides tool access"""
    
    def __init__(self):
        self.servers: Dict[str, Any] = {}  # server_id -> session info
        self.tools_cache: Dict[str, List[Dict]] = {}  # server_id -> tools list
    
    async def connect_server(self, server_id: str, command: str, args: List[str] = None, env: Dict[str, str] = None) -> bool:
        """
        Connect to an MCP server and cache its tools.
        Note: We connect, get tools, then disconnect. Tools are cached.
        Actual tool calls will reconnect on-demand.
        
        Args:
            server_id: Unique identifier for this server
            command: Command to run the MCP server (e.g., "npx", "python")
            args: Arguments for the command (e.g., ["-m", "mcp_server_fs"])
            env: Environment variables to pass to the server
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Direct stdio connection (MCP server runs on same machine as agent)
            server_params = StdioServerParameters(
                command=command,
                args=args or [],
                env=env or {}
            )
            
            # Create stdio client and connect temporarily to get tools
            # Use a timeout to prevent hanging if the server crashes
            import asyncio
            try:
                async with asyncio.timeout(10):  # 10 second timeout for connection
                    async with stdio_client(server_params) as (read, write):
                        async with ClientSession(read, write) as session:
                            # Initialize the session
                            await session.initialize()
                            
                            # List available tools
                            tools_result = await session.list_tools()
                            tools = []
                            for tool in tools_result.tools:
                                # Convert tool to dict format
                                tool_dict = {
                                    "name": tool.name,
                                    "description": tool.description or "",
                                    "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                                }
                                tools.append(tool_dict)
                            
                            # Store server config (not connection - we'll reconnect on-demand)
                            self.servers[server_id] = {
                                "params": server_params,
                                "tools": tools,
                                "command": command,
                                "args": args or [],
                                "env": env or {}
                            }
                            self.tools_cache[server_id] = tools
                            
                            print(f"[MCP] Discovered {len(tools)} tools from server {server_id}")
                            return True
            except asyncio.TimeoutError:
                print(f"[MCP] Connection to server {server_id} timed out after 10 seconds")
                return False
            except Exception as e:
                # If the server crashes during initialization (e.g., invalid path),
                # we might still be able to get tools if we catch the error early
                error_msg = str(e)
                print(f"[MCP] Error during connection to server {server_id}: {error_msg}")
                # For filesystem server, if path doesn't exist, it crashes during init
                # Try to continue anyway - tools might still be discoverable
                if "ENOENT" in error_msg or "no such file" in error_msg.lower():
                    print(f"[MCP] Path validation failed for {server_id}, but continuing...")
                    # Store empty tools list - we'll reconnect on-demand when tools are actually called
                    self.servers[server_id] = {
                        "params": server_params,
                        "tools": [],
                        "command": command,
                        "args": args or [],
                        "env": env or {}
                    }
                    self.tools_cache[server_id] = []
                    print(f"[MCP] Server {server_id} registered with empty tools (path issue - will reconnect on tool call)")
                    return True  # Return True so agent knows server exists, even if tools aren't loaded yet
                raise
                    
        except Exception as e:
            print(f"[MCP] Failed to connect to server {server_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_tools(self, server_id: Optional[str] = None) -> List[Dict]:
        """
        Get tools from a specific server or all servers
        
        Args:
            server_id: If provided, return tools from this server only
        
        Returns:
            List of tool definitions
        """
        if server_id:
            return self.tools_cache.get(server_id, [])
        else:
            # Return all tools from all servers
            all_tools = []
            for tools in self.tools_cache.values():
                all_tools.extend(tools)
            return all_tools
    
    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on an MCP server (connects on-demand)
        
        Args:
            server_id: The server ID that provides this tool
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
        
        Returns:
            Tool execution result
        """
        if server_id not in self.servers:
            raise ValueError(f"Server {server_id} not configured")
        
        try:
            server_info = self.servers[server_id]
            
            # Direct stdio connection (MCP server runs on same machine as agent)
            server_params = StdioServerParameters(
                command=server_info["command"],
                args=server_info["args"],
                env=server_info.get("env", {})
            )
            
            # Connect on-demand for tool call
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Call the tool
                    result = await session.call_tool(tool_name, arguments)
                    
                    # Convert result to dict format
                    content = []
                    if hasattr(result, 'content'):
                        for item in result.content:
                            if hasattr(item, 'type') and hasattr(item, 'text'):
                                content.append({"type": item.type, "text": item.text})
                            elif isinstance(item, dict):
                                content.append(item)
                            else:
                                content.append({"type": "text", "text": str(item)})
                    
                    is_error = getattr(result, 'isError', False)
                    
                    return {
                        "content": content,
                        "isError": is_error
                    }
                    
        except Exception as e:
            print(f"[MCP] Error calling tool {tool_name} on server {server_id}: {e}")
            import traceback
            traceback.print_exc()
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }
    
    def disconnect_server(self, server_id: str):
        """Disconnect from an MCP server"""
        if server_id in self.servers:
            del self.servers[server_id]
        if server_id in self.tools_cache:
            del self.tools_cache[server_id]
        print(f"[MCP] Disconnected from server {server_id}")
    
    def convert_mcp_tool_to_function_schema(self, mcp_tool: Dict) -> Dict:
        """
        Convert an MCP tool definition to the function schema format used by the agent
        
        Args:
            mcp_tool: MCP tool definition from list_tools()
        
        Returns:
            Function schema in the format expected by convert_tools_to_description()
        """
        # Extract tool information
        name = mcp_tool.get("name", "")
        description = mcp_tool.get("description", "")
        input_schema = mcp_tool.get("inputSchema", {})
        
        # Convert input schema to parameters format
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])
        
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


# Global MCP manager instance
mcp_manager = MCPServerManager()

