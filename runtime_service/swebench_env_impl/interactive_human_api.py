"""
Interactive Human API Service for SWE-bench tasks.

This service receives OpenAI-compatible chat completion requests from the agent,
displays the conversation to the user, waits for human input, and returns it
as the LLM response.
"""
import json
import sys
import threading
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
    """Receive agent messages, display to user, wait for human input."""
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
        
        # Format and display messages to user
        print("\n" + "="*80, flush=True)
        print(f"AGENT REQUEST [{request_id}]:", flush=True)
        print("="*80, flush=True)
        print(format_messages_for_display(messages), flush=True)
        print("="*80, flush=True)
        print(f"\n[Request ID: {request_id}]", flush=True)
        print("Please provide your response (type your message, press Enter twice to finish):", flush=True)
        print("(Or type 'SKIP' to skip this step, 'QUIT' to exit)", flush=True)
        print("> ", end="", flush=True)
        
        # Store the request
        pending_requests[request_id] = (messages, response_queue)
        
        # Wait for user input in a separate thread (non-blocking)
        def get_user_input():
            """Get user input in a separate thread."""
            user_input_lines = []
            empty_line_count = 0
            
            try:
                while True:
                    try:
                        line = input()
                        if line.strip().upper() == "QUIT":
                            response_queue.put("[User quit]")
                            break
                        elif line.strip().upper() == "SKIP":
                            response_queue.put("[Skipped by user]")
                            break
                        elif line == "":
                            empty_line_count += 1
                            if empty_line_count >= 2:
                                user_input = "\n".join(user_input_lines)
                                response_queue.put(user_input)
                                break
                        else:
                            empty_line_count = 0
                            user_input_lines.append(line)
                            print("> ", end="", flush=True)  # Continue prompt
                    except EOFError:
                        user_input = "\n".join(user_input_lines) if user_input_lines else "[No input]"
                        response_queue.put(user_input)
                        break
            except Exception as e:
                response_queue.put(f"[Error getting input: {e}]")
        
        # Start input thread
        input_thread = threading.Thread(target=get_user_input, daemon=True)
        input_thread.start()
        
        # Wait for response (with timeout)
        timeout = 3600  # 1 hour timeout
        start_time = time.time()
        user_input = None
        
        while time.time() - start_time < timeout:
            try:
                user_input = response_queue.get(timeout=1)
                break
            except:
                continue
        
        # Clean up
        if request_id in pending_requests:
            del pending_requests[request_id]
        
        if user_input is None:
            user_input = "[Timeout - no input received]"
        
        print(f"\n[Your response: {user_input[:100]}...]\n", flush=True)
        
        # Return OpenAI-compatible response
        return JSONResponse(
            status_code=200,
            content={
                "id": "chatcmpl-human",
                "object": "chat.completion",
                "created": 0,
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Interactive Human API Service")
    parser.add_argument("--port", type=int, default=8007, help="Port to run the service on")
    args = parser.parse_args()
    
    print(f"Starting Interactive Human API Service on port {args.port}")
    print("This service will display agent messages and wait for your input.")
    print("="*80)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")

