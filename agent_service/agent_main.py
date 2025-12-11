import uvicorn
import json
import asyncio
import time
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, AsyncGenerator
import uuid
import os

from config import settings
from utils.path_mapper import PathMapper
from agent.trae_wrapper import TraeAgentWrapper

app = FastAPI(title="Coding Agent Service")

# In-memory session storage with metadata
# Format: {session_id: {agent, path_mapper, history, created_at, last_accessed}}
sessions: Dict[str, Dict[str, Any]] = {}

# Session configuration
SESSION_TIMEOUT_SECONDS = 3600  # 1 hour
SESSION_CLEANUP_INTERVAL = 300  # Check every 5 minutes

class CreateSessionRequest(BaseModel):
    pass

class CreateSessionResponse(BaseModel):
    session_id: str
    workspace_path: str

class PromptRequest(BaseModel):
    prompt: str
    history: Optional[List[Dict[str, Any]]] = None
    stream: Optional[bool] = False

class PromptResponse(BaseModel):
    response: str
    history: List[Dict[str, Any]]

async def cleanup_session(session_id: str):
    """Clean up a single session's resources."""
    if session_id in sessions:
        session = sessions[session_id]

        # Cleanup agent resources
        agent = session.get("agent")
        if agent and hasattr(agent, 'cleanup'):
            try:
                await agent.cleanup()
            except Exception as e:
                print(f"Error cleaning up agent for session {session_id}: {e}")

        # Remove workspace directory
        path_mapper = session.get("path_mapper")
        if path_mapper:
            try:
                workspace_path = path_mapper.session_workspace
                if workspace_path.exists():
                    shutil.rmtree(workspace_path, ignore_errors=True)
            except Exception as e:
                print(f"Error removing workspace for session {session_id}: {e}")

        # Remove from sessions dict
        del sessions[session_id]

async def cleanup_expired_sessions():
    """Remove sessions that have exceeded the timeout."""
    current_time = time.time()
    expired_sessions = []

    for session_id, session in sessions.items():
        last_accessed = session.get("last_accessed", session.get("created_at", 0))
        if current_time - last_accessed > SESSION_TIMEOUT_SECONDS:
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        print(f"Cleaning up expired session: {session_id}")
        await cleanup_session(session_id)

@app.on_event("startup")
async def startup_event():
    """Start background task for session cleanup."""
    async def cleanup_loop():
        while True:
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
            await cleanup_expired_sessions()

    asyncio.create_task(cleanup_loop())

@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    path_mapper = PathMapper(session_id, settings.WORKSPACE_ROOT)
    path_mapper.ensure_workspace_exists()

    agent = TraeAgentWrapper(path_mapper)

    current_time = time.time()
    sessions[session_id] = {
        "agent": agent,
        "path_mapper": path_mapper,
        "history": [],
        "created_at": current_time,
        "last_accessed": current_time
    }

    return CreateSessionResponse(
        session_id=session_id,
        workspace_path=str(path_mapper.session_workspace)
    )

async def stream_agent_events(session_id: str, prompt: str, history: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
    """
    Stream agent execution events (actions and observations).
    Yields SSE-formatted events compatible with OpenAI streaming API.
    """
    session = sessions[session_id]
    agent = session["agent"]

    # Make a copy of history to avoid mutation issues during streaming
    working_history = history.copy()

    # Add user message to working history
    working_history.append({"role": "user", "content": prompt})

    # Track if we successfully got a final response
    final_response_content = None
    stream_completed = False

    try:
        # Stream events from agent execution
        async for event in agent.process_message_stream(working_history):
            event_type = event.get("type")

            if event_type == "action":
                # Agent is taking an action (e.g., calling a tool)
                chunk = {
                    "type": "action",
                    "action": event.get("action"),
                    "tool": event.get("tool"),
                    "arguments": event.get("arguments"),
                    "reasoning": event.get("reasoning", "")
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            elif event_type == "observation":
                # Agent received observation from tool execution
                chunk = {
                    "type": "observation",
                    "tool": event.get("tool"),
                    "result": event.get("result"),
                    "success": event.get("success", True)
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            elif event_type == "thinking":
                # Agent is thinking/reasoning
                chunk = {
                    "type": "thinking",
                    "content": event.get("content", "")
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            elif event_type == "response":
                # Final response from agent
                final_response_content = event.get("content", "")
                chunk = {
                    "type": "response",
                    "content": final_response_content,
                    "finished": True
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                stream_completed = True

            elif event_type == "error":
                # Error occurred
                chunk = {
                    "type": "error",
                    "error": event.get("error", "Unknown error")
                }
                yield f"data: {json.dumps(chunk)}\n\n"

        # Only update session history if stream completed successfully
        if stream_completed and final_response_content is not None:
            working_history.append({"role": "assistant", "content": final_response_content})
            session["history"] = working_history

        # Send done signal
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_chunk = {
            "type": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"

@app.post("/sessions/{session_id}/prompt")
async def prompt_agent(session_id: str, request: PromptRequest):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions[session_id]
    
    # Get history
    history = request.history if request.history else session["history"].copy()
    
    # If streaming is requested, return SSE stream
    if request.stream:
        return StreamingResponse(
            stream_agent_events(session_id, request.prompt, history),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    
    # Non-streaming response (original behavior)
    agent = session["agent"]
    history.append({"role": "user", "content": request.prompt})

    result = await agent.process_message(history)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    response_text = result.get("response", "")
    history.append({"role": "assistant", "content": response_text})
    session["history"] = history

    return PromptResponse(
        response=response_text,
        history=history
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("agent_main:app", host=settings.HOST, port=settings.PORT, reload=False)
