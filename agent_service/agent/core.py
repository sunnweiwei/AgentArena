import json
import openai
from typing import List, Dict, Any
from agent.tools import AgentTools
from config import settings

class Agent:
    def __init__(self, tools: AgentTools):
        self.tools = tools
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.system_prompt = """You are a helpful coding agent.
You have access to a workspace where you can read, write files and run commands.
You are working in a restricted environment.
The root directory is /workspace.
Always verify your actions.
When running python code, use 'python <filename>'.
"""

    def process_message(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        # Add system prompt if not present
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": self.system_prompt})

        # Define tools schema
        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List contents of a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to list, defaults to ."}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read content of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to file"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to file"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "Command to run"}
                        },
                        "required": ["command"]
                    }
                }
            }
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto"
            )

            message = response.choices[0].message
            
            if message.tool_calls:
                # Handle tool calls
                tool_outputs = []
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    
                    output = f"Error: Unknown tool {func_name}"
                    if func_name == "list_dir":
                        output = self.tools.list_dir(args.get("path", "."))
                    elif func_name == "read_file":
                        output = self.tools.read_file(args.get("path"))
                    elif func_name == "write_file":
                        output = self.tools.write_file(args.get("path"), args.get("content"))
                    elif func_name == "run_command":
                        output = self.tools.run_command(args.get("command"))
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": func_name,
                        "content": output
                    })
                
                # Return the tool calls and the outputs so the caller can append them and call again
                return {
                    "response_message": message,
                    "tool_outputs": tool_outputs,
                    "finished": False
                }
            else:
                return {
                    "response_message": message,
                    "finished": True
                }

        except Exception as e:
            return {"error": str(e), "finished": True}
