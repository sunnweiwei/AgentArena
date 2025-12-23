# MCP Filesystem Server Setup Guide

This guide sets up the Model Context Protocol (MCP) filesystem server to provide file editing capabilities for your workspace.

## Prerequisites

- Node.js 18+ and npm installed
- Your workspace directory: `/Users/sunweiwei/NLP/base_project`

## Installation Steps

### 1. Install MCP Filesystem Server globally

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

Or install locally in your project:

```bash
npm install @modelcontextprotocol/server-filesystem
```

### 2. Verify Installation

```bash
# Check if installed
npx @modelcontextprotocol/server-filesystem --help
```

## Configuration

### MCP Server Configuration (mcp_config.json)

Create a file `mcp_config.json` in your project root:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/sunweiwei/NLP/base_project"
      ],
      "env": {}
    }
  }
}
```

### Alternative: Direct Node.js Execution

If you installed locally:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": [
        "node_modules/@modelcontextprotocol/server-filesystem/dist/index.js",
        "/Users/sunweiwei/NLP/base_project"
      ],
      "env": {}
    }
  }
}
```

## Usage

The filesystem MCP server provides these capabilities:

### Available Tools

1. **read_file** - Read complete contents of a file
   ```json
   {
     "path": "path/to/file.txt"
   }
   ```

2. **read_multiple_files** - Read multiple files at once
   ```json
   {
     "paths": ["file1.txt", "file2.py"]
   }
   ```

3. **write_file** - Create or overwrite a file
   ```json
   {
     "path": "path/to/file.txt",
     "content": "file contents"
   }
   ```

4. **edit_file** - Make selective edits using advanced pattern matching
   ```json
   {
     "path": "path/to/file.py",
     "edits": [
       {
         "oldText": "old code",
         "newText": "new code"
       }
     ],
     "dryRun": false
   }
   ```

5. **create_directory** - Create a new directory
   ```json
   {
     "path": "path/to/new/directory"
   }
   ```

6. **list_directory** - List directory contents
   ```json
   {
     "path": "path/to/directory"
   }
   ```

7. **move_file** - Move or rename files
   ```json
   {
     "source": "old/path.txt",
     "destination": "new/path.txt"
   }
   ```

8. **search_files** - Search for files by pattern
   ```json
   {
     "path": ".",
     "pattern": "*.py",
     "excludePatterns": ["node_modules", "__pycache__"]
   }
   ```

9. **get_file_info** - Get metadata about a file
   ```json
   {
     "path": "path/to/file.txt"
   }
   ```

10. **list_allowed_directories** - List all allowed directories

## Security

The MCP filesystem server only has access to the directories you explicitly allow:
- Allowed: `/Users/sunweiwei/NLP/base_project` (and subdirectories)
- Blocked: Everything outside this directory

## Testing

Test the server manually:

```bash
# Start the server
npx @modelcontextprotocol/server-filesystem /Users/sunweiwei/NLP/base_project

# The server will listen for MCP protocol messages on stdin/stdout
```

## Integration with Your Agent System

To integrate with your agent system, you need to:

1. **Add MCP client support** to your agent
2. **Configure the MCP server** in your agent's config
3. **Map MCP tools** to your agent's tool calling system

Example Python MCP client integration:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def connect_to_filesystem_mcp():
    server_params = StdioServerParameters(
        command="npx",
        args=[
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "/Users/sunweiwei/NLP/base_project"
        ],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("Available tools:", tools)

            # Call a tool
            result = await session.call_tool(
                "read_file",
                {"path": "README.md"}
            )
            print("File contents:", result)

# Run
asyncio.run(connect_to_filesystem_mcp())
```

## Troubleshooting

### Error: Command not found
- Ensure Node.js is installed: `node --version`
- Ensure npm is installed: `npm --version`
- Try installing globally: `npm install -g @modelcontextprotocol/server-filesystem`

### Error: Permission denied
- Check directory permissions: `ls -la /Users/sunweiwei/NLP/base_project`
- Ensure your user has read/write access to the workspace

### Server not responding
- Check if the server is running
- Verify the path is correct and absolute
- Check server logs for errors

## Next Steps

1. Install the MCP filesystem server
2. Test it with the provided commands
3. Integrate it into your agent system using the config
4. Add MCP client library to your agent dependencies
