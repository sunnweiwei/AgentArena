"""Wrapper for Trae Agent to work with our service requirements."""

import os
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from pathlib import Path

from trae_agent.agent.trae_agent import TraeAgent
from trae_agent.utils.config import TraeAgentConfig, ModelConfig
from trae_agent.utils.llm_clients.llm_client import LLMProvider
from utils.path_mapper import PathMapper
from config import settings


class TraeAgentWrapper:
    """Wrapper for Trae Agent with workspace isolation and path mapping."""
    
    def __init__(self, path_mapper: PathMapper):
        self.path_mapper = path_mapper
        self.agent = None
        self.initialized = False
        
    async def _ensure_initialized(self):
        """Ensure the agent is initialized."""
        if not self.initialized:
            # Import ModelProvider
            from trae_agent.utils.config import ModelProvider
            
            # Create model provider
            model_provider = ModelProvider(
                api_key=settings.OPENAI_API_KEY,
                provider="openai",
                base_url=None
            )
            
            # Create model config
            model_config = ModelConfig(
                model=settings.OPENAI_MODEL,
                model_provider=model_provider,
                temperature=0.7,
                top_p=1.0,
                top_k=0,
                parallel_tool_calls=True,
                max_retries=3
            )
            
            # Create agent config
            agent_config = TraeAgentConfig(
                model=model_config,
                max_steps=15,  # Allow more steps for complex tasks
                allow_mcp_servers=[],
                mcp_servers_config={},
            )
            
            # Create agent (no docker, we use path mapping)
            self.agent = TraeAgent(
                trae_agent_config=agent_config,
                docker_config=None,
                docker_keep=False
            )
            
            # Initialize MCP if needed
            await self.agent.initialise_mcp()
            self.initialized = True
        
    async def process_message(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a message using Trae Agent.

        Trae Agent uses its own tools:
        - bash: Execute shell commands
        - str_replace_based_edit_tool: Edit files with string replacement
        - json_edit_tool: Edit JSON files
        - sequentialthinking: Break down complex tasks
        - task_done: Mark task as complete

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Dict with 'response', 'finished', and optionally 'error'
        """
        # Extract the user's task from messages
        user_messages = [m for m in messages if m.get('role') == 'user']
        if not user_messages:
            return {"error": "No user message found", "finished": True}

        task = user_messages[-1].get('content', '')

        # Run the agent asynchronously
        try:
            result = await self._run_agent(task)
            return result
        except Exception as e:
            return {"error": str(e), "finished": True}
    
    async def process_message_stream(self, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a message using Trae Agent with streaming support.
        Yields events during the agent loop (action, observation, thinking, response).
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Yields:
            Dict events with type and relevant data
        """
        # Extract the user's task from messages
        user_messages = [m for m in messages if m.get('role') == 'user']
        if not user_messages:
            yield {"type": "error", "error": "No user message found"}
            return
        
        task = user_messages[-1].get('content', '')
        
        try:
            # Ensure agent is initialized
            await self._ensure_initialized()
            
            yield {"type": "thinking", "content": "Initializing agent..."}
            
            # Prepare extra args with workspace path
            extra_args = {
                "project_path": str(self.path_mapper.session_workspace),
                "issue": task,
            }
            
            # Create new task
            self.agent.new_task(
                task=task,
                extra_args=extra_args,
                tool_names=None
            )
            
            yield {"type": "thinking", "content": "Agent is analyzing the task..."}
            
            # Execute task - we'll monitor the execution
            # Since we can't easily intercept trae-agent's internal loop,
            # we'll execute it and emit simulated events
            execution = await self.agent.execute_task()
            
            # Emit a generic action event
            yield {
                "type": "action",
                "action": "Executing task with trae-agent tools",
                "tool": "trae-agent",
                "arguments": {"task": task},
                "reasoning": "Using optimized tools: bash, str_replace_based_edit_tool, json_edit_tool, sequentialthinking, task_done"
            }
            
            # Emit observation
            yield {
                "type": "observation",
                "tool": "trae-agent",
                "result": f"Task execution {'successful' if execution.success else 'failed'}",
                "success": execution.success
            }
            
            # Emit final response
            yield {
                "type": "response",
                "content": execution.final_result or "Task completed"
            }
                
        except Exception as e:
            yield {"type": "error", "error": str(e)}
    
    async def _run_agent(self, task: str) -> Dict[str, Any]:
        """Run the agent on a task."""
        # Ensure agent is initialized
        await self._ensure_initialized()
        
        # Prepare extra args with workspace path
        # Trae agent expects project_path to be the working directory
        extra_args = {
            "project_path": str(self.path_mapper.session_workspace),
            "issue": task,
        }
        
        # Create new task with trae-agent's tools
        # This will use: bash, str_replace_based_edit_tool, json_edit_tool, 
        # sequentialthinking, task_done
        self.agent.new_task(
            task=task,
            extra_args=extra_args,
            tool_names=None  # Use default trae-agent tools
        )
        
        # Execute task - trae-agent handles all the tool execution internally
        execution = await self.agent.execute_task()
        
        # Return result
        return {
            "response": execution.final_result or "Task completed",
            "finished": True,
            "success": execution.success,
        }
    
    async def cleanup(self):
        """Clean up resources."""
        if self.agent:
            await self.agent.cleanup_mcp_clients()
