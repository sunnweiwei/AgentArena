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
        tools = body.get("tools", [])
        
        # Generate a unique request ID
        with request_lock:
            request_counter += 1
            request_id = f"req_{request_counter}"
        
        # Create a queue for the response
        response_queue = Queue()
        
        # Store the request (messages and response queue)
        pending_requests[request_id] = (messages, tools, response_queue)
        
        # Log the new request
        print(f"\n[New pending request {request_id}] Created. Waiting for response via submit_response().", flush=True)
        
        # Wait for response from submit_response (with timeout)
        # Use asyncio to avoid blocking the event loop
        timeout = 3600  # 1 hour timeout
        start_time = time.time()
        response_data = None
        
        while time.time() - start_time < timeout:
            try:
                # Try to get response from queue (non-blocking with timeout)
                # Run blocking queue.get() in a thread to avoid blocking event loop
                loop = asyncio.get_event_loop()
                try:
                    # Use timeout parameter correctly for queue.get()
                    response_data = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: response_queue.get(timeout=1)),
                        timeout=1.1  # Slightly longer than queue timeout
                    )
                    break
                except asyncio.TimeoutError:
                    # asyncio timeout, continue waiting
                    await asyncio.sleep(0.1)  # Small async sleep to yield control
                    continue
            except Exception as e:
                # Catch queue.Empty and other exceptions
                from queue import Empty
                if isinstance(e, Empty) or "Empty" in str(type(e)):
                    # Queue is empty, continue waiting
                    await asyncio.sleep(0.1)
                    continue
                # Other errors, log and continue
                print(f"[Warning] Error waiting for response: {e}", flush=True)
                await asyncio.sleep(0.1)
                continue
        
        # Clean up the pending request IMMEDIATELY after getting response
        # This prevents duplicate submissions from finding the request
        if request_id in pending_requests:
            del pending_requests[request_id]
            print(f"[Request {request_id}] Removed from pending_requests after receiving response", flush=True)
        
        # Parse response data
        if response_data is None:
            user_input = "[Timeout - no response received]"
            tool_calls = []
            print(f"\n[Request {request_id}] Timeout waiting for response.", flush=True)
        else:
            # Handle both old format (string) and new format (dict)
            if isinstance(response_data, dict):
                user_input = response_data.get("response", "")
                tool_calls = response_data.get("tool_calls", [])
            else:
                # Backward compatibility: if it's a string, treat as old format
                user_input = response_data
                tool_calls = []
            
            print(f"\n[Request {request_id}] Response received: {user_input[:100]}...", flush=True)
            if tool_calls:
                print(f"[Request {request_id}] Tool calls received: {len(tool_calls)} tool call(s)", flush=True)
        
        # Build message object
        message = {
            "role": "assistant",
            "content": user_input
        }

        # Add tool_calls if present
        if tool_calls:
            message["tool_calls"] = tool_calls
        
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
                    "message": message,
                    "finish_reason": "tool_calls" if tool_calls else "stop"
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
        "pending_requests": len(pending_requests),
        "pending_request_ids": list(pending_requests.keys())
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
    messages, tools, _ = pending_requests[latest_request_id]
    
    tools_instruction = """You have the following tools available:\n"""
    for tool in tools:
        tools_instruction += json.dumps(tool)
        tools_instruction += "\n\n"
    messages.insert(1, {"role": "system", "content": tools_instruction})
    
    return {
        "observation": messages,
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
        tool_calls = body.get("tool_calls", [])
        
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
        
        messages, tools, response_queue = pending_requests[request_id]
        
        # Check if queue is already full (meaning response was already submitted)
        # This prevents duplicate submissions
        if not response_queue.empty():
            print(f"[Request {request_id}] WARNING: Queue already has data, previous response may not have been processed yet", flush=True)
            # Still put the new response, but log a warning
            # The chat_completions endpoint will only get the first one
        
        # Put response and tool_calls in queue (this will wake up the waiting chat_completions)
        # Package both response and tool_calls together
        response_data = {
            "response": response,
            "tool_calls": tool_calls if tool_calls else []
        }
        response_queue.put(response_data)
        
        print(f"[Request {request_id}] Response submitted: {response[:100]}...", flush=True)
        if tool_calls:
            print(f"[Request {request_id}] Tool calls submitted: {len(tool_calls)} tool call(s)", flush=True)
        
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

