"""
Interactive Human API Service for SWE-bench tasks.

This service receives OpenAI-compatible chat completion requests from the agent,
displays the conversation to the user, waits for human input, and returns it
as the LLM response.
"""
import json
import sys
import threading
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from queue import Queue
from typing import Optional, Dict
import time

app = FastAPI()

# Store pending requests and responses
# Key: request_id, Value: (request_data, response_queue)
pending_requests: Dict[str, tuple] = {}
request_counter = 0
request_lock = threading.Lock()


def format_messages_for_display(messages):
    """Format messages for human-readable display."""
    formatted = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if role == "system":
            formatted.append(f"=== SYSTEM ===\n{content}\n")
        elif role == "user":
            formatted.append(f"=== USER ===\n{content}\n")
        elif role == "assistant":
            formatted.append(f"=== ASSISTANT ===\n{content}\n")
        elif role == "tool":
            formatted.append(f"=== TOOL CALL: {msg.get('name', 'unknown')} ===\n{content}\n")
        else:
            formatted.append(f"=== {role.upper()} ===\n{content}\n")
    return "\n".join(formatted)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Receive agent messages, create a pending request, and wait for response.
    
    This endpoint:
    1. Creates a pending request that can be retrieved via get_observation()
    2. Waits for response to be submitted via submit_response()
    3. Returns the response to the workspace
    
    The request is stored in pending_requests, and the response is provided
    through the response_queue.
    """
    global request_counter
    
    try:
        body = await request.json()
        messages = body.get("messages", [])
        
        # Generate a unique request ID
        with request_lock:
            request_counter += 1
            request_id = f"req_{request_counter}"
        
        # Create a queue for the response
        response_queue = Queue()
        
        # Store the request (messages and response queue)
        pending_requests[request_id] = (messages, response_queue)
        
        # Log the new request
        print(f"\n[New pending request {request_id}] Created. Waiting for response via submit_response().", flush=True)
        
        # Wait for response from submit_response (with timeout)
        # Use asyncio to avoid blocking the event loop
        timeout = 3600  # 1 hour timeout
        start_time = time.time()
        user_input = None
        
        while time.time() - start_time < timeout:
            try:
                # Try to get response from queue (non-blocking with timeout)
                # Run blocking queue.get() in a thread to avoid blocking event loop
                loop = asyncio.get_event_loop()
                try:
                    user_input = await asyncio.wait_for(
                        loop.run_in_executor(None, response_queue.get, 1),
                        timeout=1.1  # Slightly longer than queue timeout
                    )
                    break
                except asyncio.TimeoutError:
                    # Queue is empty, continue waiting
                    await asyncio.sleep(0.1)  # Small async sleep to yield control
                    continue
            except Exception as e:
                # Other errors, log and continue
                print(f"[Warning] Error waiting for response: {e}", flush=True)
                await asyncio.sleep(0.1)
                continue
        
        # Clean up the pending request after getting response
        if request_id in pending_requests:
            del pending_requests[request_id]
        
        if user_input is None:
            user_input = "[Timeout - no response received]"
            print(f"\n[Request {request_id}] Timeout waiting for response.", flush=True)
        else:
            print(f"\n[Request {request_id}] Response received: {user_input[:100]}...", flush=True)
        
        # Return OpenAI-compatible response
        return JSONResponse(
            status_code=200,
            content={
                "id": f"chatcmpl-{request_id}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "human",
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": user_input
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e)}}
        )


@app.get("/health")
async def health():
    return {"status": "healthy", "type": "interactive_human_api"}


@app.get("/status")
async def status():
    return {
        "status": "running",
        "type": "interactive_human_api",
        "pending_requests": len(pending_requests)
    }


@app.get("/observation")
async def get_observation():
    """
    Get the current observation/question from workspace.
    Returns the latest pending request's messages formatted as observation.
    """
    if not pending_requests:
        return {
            "observation": "No pending observations. Waiting for workspace to send a question.",
            "has_pending": False
        }
    
    # Get the most recent request (last one in dict)
    # Note: dicts maintain insertion order in Python 3.7+
    latest_request_id = list(pending_requests.keys())[-1]
    messages, _ = pending_requests[latest_request_id]
    
    # Format messages as observation
    observation = format_messages_for_display(messages)
    
    return {
        "observation": observation,
        "request_id": latest_request_id,
        "has_pending": True
    }


@app.post("/submit_response")
async def submit_response(request: Request):
    """
    Submit human response for a pending request.
    
    Body should contain: {"request_id": "...", "response": "..."}
    
    This will put the response in the queue for the corresponding request,
    which will then be returned by the chat_completions endpoint that is
    waiting for it.
    """
    try:
        body = await request.json()
        request_id = body.get("request_id")
        response = body.get("response", "")
        
        if not request_id:
            return JSONResponse(
                status_code=400,
                content={"error": "request_id is required"}
            )
        
        if request_id not in pending_requests:
            return JSONResponse(
                status_code=404,
                content={"error": f"Request ID {request_id} not found"}
            )
        
        _, response_queue = pending_requests[request_id]
        
        # Put response in queue (this will wake up the waiting chat_completions)
        response_queue.put(response)
        
        print(f"[Request {request_id}] Response submitted: {response[:100]}...", flush=True)
        
        return {
            "success": True,
            "message": f"Response submitted for request {request_id}",
            "request_id": request_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Interactive Human API Service")
    parser.add_argument("--port", type=int, default=8007, help="Port to run the service on")
    args = parser.parse_args()
    
    print(f"Starting Interactive Human API Service on port {args.port}")
    print("This service will display agent messages and wait for your input.")
    print("="*80)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")

