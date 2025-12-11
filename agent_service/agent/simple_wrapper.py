"""
Simple wrapper that uses OpenAI API directly for the agent.
Uses OpenAI's chat.completions.create() API.
"""

import os
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from pathlib import Path
from openai import OpenAI

from utils.path_mapper import PathMapper
from config import settings


class SimpleAgentWrapper:
    """Simple agent wrapper using OpenAI API directly."""
    
    def __init__(self, path_mapper: PathMapper):
        self.path_mapper = path_mapper
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    async def process_message(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a message using OpenAI API directly.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Dict with 'response', 'finished'
        """
        # Extract the user's task
        user_messages = [m for m in messages if m.get('role') == 'user']
        if not user_messages:
            return {"error": "No user message found", "finished": True}

        task = user_messages[-1].get('content', '')

        try:
            # Call OpenAI API with correct chat completions endpoint
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful coding assistant. Your workspace is at {self.path_mapper.session_workspace}. Create files and run commands as needed."
                    },
                    {
                        "role": "user",
                        "content": task
                    }
                ],
                temperature=0.7
            )

            return {
                "response": response.choices[0].message.content,
                "finished": True,
                "success": True
            }
        except Exception as e:
            return {"error": str(e), "finished": True}
    
    async def process_message_stream(self, messages: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a message with streaming using OpenAI API.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Yields:
            Dict events with type and relevant data
        """
        # Extract the user's task
        user_messages = [m for m in messages if m.get('role') == 'user']
        if not user_messages:
            yield {"type": "error", "error": "No user message found"}
            return

        task = user_messages[-1].get('content', '')

        try:
            yield {"type": "thinking", "content": "Initializing OpenAI agent..."}

            # Call OpenAI API with streaming using correct chat completions endpoint
            stream = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful coding assistant. Your workspace is at {self.path_mapper.session_workspace}. Create files and run commands as needed. Explain your steps clearly."
                    },
                    {
                        "role": "user",
                        "content": task
                    }
                ],
                temperature=0.7,
                stream=True
            )

            yield {"type": "thinking", "content": "Agent is processing..."}

            full_response = ""
            for chunk in stream:
                # Stream each chunk from OpenAI
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_text = chunk.choices[0].delta.content
                    full_response += chunk_text

                    # Yield as thinking event (streaming text)
                    yield {
                        "type": "thinking",
                        "content": chunk_text
                    }

            # Emit final response
            yield {
                "type": "response",
                "content": full_response or "Task completed"
            }

        except Exception as e:
            yield {"type": "error", "error": str(e)}
    
    async def cleanup(self):
        """Clean up resources."""
        pass
