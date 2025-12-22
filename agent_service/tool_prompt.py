import re
from typing import List, Dict, Optional

# Tool prompt template
TOOL_PROMPT = """{description}

To call a function, use the following format:
<function=function_name>
<parameter=param_name>param_value</parameter>
</function>

You can call multiple functions in sequence. Make sure to use the correct format with <parameter=param_name> tags."""


def extract_fn_call(text):
    """
    Extract function calls from text. Returns:
    - List of function call dicts if valid format found
    - {'error': 'message'} if wrong format detected
    - None if no function call found
    """
    if not text:
        return None
    text = re.split(r'<\[[^\]]+\]>', text)[-1].strip()
    matches = list(re.finditer(r'(?m)^[ \t]*<function=([^>]+)>\s*(.*?)\s*</function>',
                               text, re.DOTALL))
    if not matches:
        return None
    
    # Check for wrong format: <param_name>value</param_name> instead of <parameter=param_name>value</parameter>
    for m in matches:
        fn_body = m.group(2)
        # Check if using correct format
        correct_params = re.findall(r'<parameter=([^>]+)>(.*?)</parameter>', fn_body, re.DOTALL)
        # Check if using wrong format (XML-style tags without 'parameter=')
        wrong_params = re.findall(r'<([a-z_][a-z0-9_]*)>(.*?)</\1>', fn_body, re.DOTALL | re.IGNORECASE)
        # Filter out any that might be legitimate tags
        wrong_params = [(name, val) for name, val in wrong_params if name.lower() not in ['function', 'parameter']]
        
        if wrong_params and not correct_params:
            # Agent used wrong format
            fn_name = m.group(1)
            wrong_param_names = [p[0] for p in wrong_params]
            return {
                'error': f"""**Tool Call Format Error**

You used the wrong format for function parameters. 

**Your format (WRONG):**
```
<function={fn_name}>
<{wrong_param_names[0]}>value</{wrong_param_names[0]}>
</function>
```

**Correct format:**
```
<function={fn_name}>
<parameter={wrong_param_names[0]}>value</parameter>
</function>
```

Please use `<parameter=PARAM_NAME>value</parameter>` format for all parameters."""
            }
    
    groups = [[matches[0]]]
    for m in matches[1:]:
        prev = groups[-1][-1]
        line_gap = text.count('\n', prev.end(), m.start())
        groups[-1].append(m) if line_gap < 4 else groups.append([m])
    last = groups[-1]
    return [
        {
            'name': m.group(1),
            'function': m.group(1),  # Also include 'function' key for compatibility
            'arguments': dict(re.findall(r'<parameter=([^>]+)>(.*?)</parameter>',
                                         m.group(2), re.DOTALL))
        }
        for m in last
    ]


def convert_tools_to_description(tools: List[Dict]) -> str:
    """Convert a list of tools to a formatted description string."""
    if not tools:
        return "No tools available."
    
    descriptions = []
    for tool in tools:
        # Handle different tool formats
        if isinstance(tool, dict):
            # Check if it's OpenAI function format
            if 'function' in tool:
                func = tool['function']
                name = func.get('name', 'unknown')
                desc = func.get('description', 'No description')
                params = func.get('parameters', {}).get('properties', {})
                required = func.get('parameters', {}).get('required', [])
            # Check if it's direct format
            elif 'name' in tool:
                name = tool.get('name', 'unknown')
                desc = tool.get('description', 'No description')
                params = tool.get('parameters', {}).get('properties', {}) if 'parameters' in tool else {}
                required = tool.get('parameters', {}).get('required', []) if 'parameters' in tool else []
            else:
                continue
            
            tool_desc = f"**{name}**: {desc}\n"
            if params:
                tool_desc += "Parameters:\n"
                for param_name, param_info in params.items():
                    param_type = param_info.get('type', 'string')
                    param_desc = param_info.get('description', '')
                    required_marker = " (required)" if param_name in required else ""
                    tool_desc += f"  - {param_name} ({param_type}){required_marker}: {param_desc}\n"
            descriptions.append(tool_desc)
    
    return "\n".join(descriptions)


def search_tool() -> List[Dict]:
    """Return the search tool definition."""
    return [{
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the web for information using Tavily search API",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5)"
                    }
                },
                "required": ["query"]
            }
        }
    }, {
        "type": "function",
        "function": {
            "name": "extract",
            "description": "Extract content from a URL using Tavily extract API",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to extract content from"
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional query to filter/extract specific content"
                    }
                },
                "required": ["url"]
            }
        }
    }]


def get_mcp_tools(mcp_servers: Optional[List] = None) -> tuple[List[Dict], Dict]:
    """
    Get MCP tools from servers.
    Returns: (tool_list, tool_map) where tool_map maps tool_name -> (server_id, server_config)
    """
    if not mcp_servers:
        return [], {}
    
    try:
        from mcp_manager import mcp_manager
    except ImportError:
        return [], {}
    
    tool_list = []
    tool_map = {}
    
    for server in mcp_servers:
        server_id = server.get('server_id')
        if not server_id:
            continue
        
        try:
            tools = mcp_manager.get_tools(server_id)
            for tool in tools:
                # Convert MCP tool to function schema format
                function_schema = mcp_manager.convert_mcp_tool_to_function_schema(tool)
                tool_list.append({
                    "type": "function",
                    "function": function_schema
                })
                tool_map[function_schema['name']] = (server_id, server)
        except Exception as e:
            print(f"Error getting tools from MCP server {server_id}: {e}")
            continue
    
    return tool_list, tool_map

