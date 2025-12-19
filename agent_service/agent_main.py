"""
Search Agent Server
Provides a streaming API for the search agent that's compatible with OpenAI's streaming format.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from agent_service.search_agent import agent_loop as search_agent_loop
from agent_service.tau_agent import agent_loop as tau_agent_loop
import json
import os

app = FastAPI(title="Search Agent Server")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = True
    meta_info: str = ""

async def generate_stream(messages: List[Dict[str, str]], agent_loop, meta_info: str = ""):
    """
    Generate streaming response in OpenAI-compatible format.
    Yields Server-Sent Events (SSE) format.
    Supports cancellation when client disconnects.
    """
    import asyncio
    import threading
    import queue

    # Create a cancel event for the agent loop
    cancel_event = threading.Event()
    chunk_queue = queue.Queue()
    error_holder = [None]  # Mutable to capture errors from thread

    def run_agent_loop():
        """Run the agent loop in a separate thread and put chunks in queue"""
        try:
            import sys
            print(f"[run_agent_loop] Starting agent loop with agent: {agent_loop.__name__}")
            sys.stdout.flush()
            conversation = [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            print(f"[run_agent_loop] Calling agent_loop with conversation: {conversation[:1]}")
            sys.stdout.flush()
            for chunk in agent_loop(conversation, cancel_event, meta_info):
                if cancel_event.is_set():
                    print("[run_agent_loop] Cancel detected, stopping")
                    sys.stdout.flush()
                    break
                if chunk:
                    print(f"[run_agent_loop] Received chunk type: {type(chunk)}, is_dict: {isinstance(chunk, dict)}")
                    sys.stdout.flush()
                    # Check if chunk is a dict (info) or string (content)
                    if isinstance(chunk, dict) and 'info' in chunk:
                        chunk_queue.put(("info", chunk['info']))
                    else:
                        chunk_queue.put(("chunk", chunk))
            print("[run_agent_loop] Agent loop completed, sending done")
            sys.stdout.flush()
            chunk_queue.put(("done", None))
        except Exception as e:
            import traceback
            print(f"[run_agent_loop] EXCEPTION: {e}")
            sys.stdout.flush()
            traceback.print_exc()
            error_holder[0] = e
            chunk_queue.put(("error", str(e)))

    # Start agent loop in background thread
    agent_thread = threading.Thread(target=run_agent_loop, daemon=True)
    agent_thread.start()

    try:
        while True:
            try:
                # Use asyncio to check queue with timeout, allowing cancellation
                event_type, data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: chunk_queue.get(timeout=0.5)
                )
            except queue.Empty:
                # No data yet, yield control and check again
                await asyncio.sleep(0)
                continue

            if event_type == "done":
                break
            elif event_type == "error":
                error_data = {
                    "error": {
                        "message": data,
                        "type": "server_error"
                    }
                }
                yield f"data: {json.dumps(error_data)}\n\n"
                return
            elif event_type == "info":
                # Send info update as SSE
                info_data = data
                sse_info = f"info: {info_data}\n\n"
                print(f"[Stream] Yielding info: {len(data)} chars")
                yield sse_info
                await asyncio.sleep(0)
            elif event_type == "chunk":
                chunk_data = {
                    "choices": [{
                        "delta": {
                            "content": data
                        },
                        "index": 0,
                        "finish_reason": None
                    }]
                }
                sse_data = f"data: {json.dumps(chunk_data)}\n\n"
                print(f"[Stream] Yielding chunk: {len(data)} chars")
                yield sse_data
                await asyncio.sleep(0)

        # Send final chunk indicating completion
        final_data = {
            "choices": [{
                "delta": {},
                "index": 0,
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_data)}\n\n"
        yield "data: [DONE]\n\n"

    except asyncio.CancelledError:
        # Client disconnected - signal the agent loop to stop
        print("[generate_stream] Client disconnected, cancelling agent loop")
        cancel_event.set()
        raise
    except GeneratorExit:
        # Client closed connection
        print("[generate_stream] Generator exit, cancelling agent loop")
        cancel_event.set()
        raise
    except Exception as e:
        import traceback
        print(f"Error in generate_stream: {e!r}")
        print(f"generate_stream error type: {type(e).__name__}")
        traceback.print_exc()
        cancel_event.set()  # Stop agent loop on any error
        error_data = {
            "error": {
                "message": str(e) or type(e).__name__,
                "type": "server_error"
            }
        }
        yield f"data: {json.dumps(error_data)}\n\n"
    finally:
        # Ensure cancel is set when generator closes
        cancel_event.set()


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """
    OpenAI-compatible chat completions endpoint with streaming support.
    """
    conversation = [msg.dict() for msg in request.messages]
    if conversation[0]['role'] == 'user' and conversation[0]['content'].startswith('\\tau'):
        selected_agent_loop = tau_agent_loop
    else:
        selected_agent_loop = search_agent_loop
    if request.stream:
        return StreamingResponse(
            generate_stream(conversation, selected_agent_loop, request.meta_info),
            media_type="text/event-stream"
        )
    else:
        # Non-streaming response (collect all chunks)
        import threading
        cancel_event = threading.Event()
        full_response = ""
        for chunk in selected_agent_loop(conversation, cancel_event, request.meta_info):
            # Only accumulate string chunks, skip info dicts
            if isinstance(chunk, str):
                full_response += chunk
        return {"choices": [{"message": {"role": "assistant", "content": full_response}, "index": 0,
                             "finish_reason": "stop"}]}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Agent Server", "version": "1.0.0",
            "endpoints": {"chat": "/v1/chat/completions", "health": "/health"}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
