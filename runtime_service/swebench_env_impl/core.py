import hashlib
import json
import os
import sys
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

def _start_interactive_human_api_service(port: int = 8007) -> subprocess.Popen:
    """
    Start an interactive human API service that allows human input for SWE-bench tasks.
    
    This service receives OpenAI-compatible chat completion requests from the agent,
    displays the conversation to the user, waits for human input, and returns it
    as the LLM response.
    
    Args:
        port: Port to run the interactive API service on
    
    Returns:
        subprocess.Popen object for the interactive API service
    
    The service provides:
    - POST /v1/chat/completions: Receives agent messages, shows to user, waits for input
    - GET /health: Health check endpoint
    - GET /status: Get current status
    """
    try:
        # Get the path to the interactive_human_api.py script
        script_dir = Path(__file__).parent
        interactive_script_path = script_dir / "interactive_human_api.py"
        
        if not interactive_script_path.exists():
            raise FileNotFoundError(
                f"Interactive human API script not found at {interactive_script_path}"
            )

        # Start the service
        # Important: stdin must be connected so input() can work
        process = subprocess.Popen(
            [sys.executable, str(interactive_script_path), "--port", str(port)],
            stdout=sys.stdout,  # Direct output to console so user can see prompts
            stderr=sys.stderr,
            stdin=sys.stdin,    # Connect stdin so input() can read from terminal
            text=True,
        )
        
        # Wait a bit for the service to start
        time.sleep(10)
        
        # Check if process is still running
        if process.poll() is not None:
            raise RuntimeError(
                f"Failed to start interactive human API service"
            )
        
        # Verify the service is running by checking health endpoint
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/health", timeout=2) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Interactive API health check failed: {resp.status}")
        except Exception as e:
            raise RuntimeError(f"Interactive API service not responding: {e}")
        
        return process
    except Exception as e:
        raise RuntimeError(f"Failed to start interactive human API service: {e}")


def create_interactive_llm_config(interactive_api_url: str = "http://sf.lti.cs.cmu.edu:8007") -> dict:
    """
    Create an LLM config that points to the interactive human API service.
    
    Args:
        interactive_api_url: URL of the interactive human API service
    
    Returns:
        Dictionary with LLM configuration pointing to the interactive service
    """
    return {
        "model": "gpt-4o-mini",  # Model name doesn't matter, but required by LLM class
        "base_url": f"{interactive_api_url}/v1",
        "api_key": "not-needed",  # Not used by interactive service, but required by LLM class
    }

@dataclass
class SweBenchInteractiveEnv:
    """
    A lightweight, problem-centric interactive environment for SWE-bench.
    
    This class manages the interactive human API service that acts as a bridge
    between the workspace/server and human input. The workspace sends questions
    to the API, and this environment retrieves observations and submits human responses.
    
    Example:
        # Start interactive environment
        env = SweBenchInteractiveEnv(
            dataset_name="princeton-nlp/SWE-bench_Verified",
            instance_id="django__django-11333",
        )
        
        # Get LLM config pointing to the interactive service
        llm_config_path = env.get_llm_config_path()
        
        # Get current observation from workspace
        observation = env.get_observations()
        
        # Submit human response
        result = env.step({"response": "human's answer"})
        
        # Clean up when done
        env.close()
    """
    
    dataset_name: str
    split: str = "test"
    instance_id: Optional[str] = None
    instance_index: Optional[int] = None
    interactive_api_port: int = 8055
    
    # Interactive API service process
    interactive_api_process: Optional[subprocess.Popen] = field(default=None, init=False)
    # Path to temporary LLM config file
    llm_config_path: Optional[str] = field(default=None, init=False)
    # Base URL for interactive API
    interactive_api_url: str = field(default="", init=False)
    # Current pending request ID (set by get_observations)
    current_request_id: Optional[str] = field(default=None, init=False)
    # Counter for tool call IDs
    tool_call_counter: int = field(default=0, init=False)
    last_observation: Optional[str] = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        """Initialize interactive environment and start API service."""
        # Start interactive API service
        self.interactive_api_process = _start_interactive_human_api_service(
            port=self.interactive_api_port
        )
        
        # Set interactive API URL
        self.interactive_api_url = os.getenv(
            "INTERACTIVE_API_URL", f"http://sf.lti.cs.cmu.edu:{self.interactive_api_port}"
        )
        
        # Create LLM config file pointing to interactive service
        llm_config_dict = create_interactive_llm_config(self.interactive_api_url)
        
        # Save to logs directory
        log_folder = Path(__file__).parent / "logs"
        log_folder.mkdir(exist_ok=True)
        
        # Generate a unique filename
        import uuid
        config_filename = f"llm_config_{uuid.uuid4().hex[:8]}.json"
        self.llm_config_path = str(log_folder / config_filename)
        
        with open(self.llm_config_path, 'w') as f:
            json.dump(llm_config_dict, f, indent=2)

        # Start test_single_task in background thread to avoid blocking __post_init__
        # This allows create_env() to return quickly while the task runs in the background
        def run_task_in_background():
            try:
                from runtime_service.swebench_env_impl.load_single_task import test_single_task
                test_single_task(
                    instance_id=self.instance_id,
                    llm_config_path=self.llm_config_path,
                )
            except Exception as e:
                print(f"Error running test_single_task in background: {e}")
                import traceback
                traceback.print_exc()

        # Start background thread
        task_thread = threading.Thread(target=run_task_in_background, daemon=True)
        task_thread.start()
    
    def _calculate_observation_delta(self, current_observation):
        """
        Calculate the delta (new content) between current and last observation.
        
        Args:
            current_observation: Current observation (can be list of messages or string)
        
        Returns:
            Delta observation (new content only), can be list or string
        """
        if self.last_observation is None:
            # First observation, return everything
            if isinstance(current_observation, list):
                return current_observation
            else:
                return current_observation
        
        # If both are lists (messages), find new messages
        if isinstance(current_observation, list) and isinstance(self.last_observation, list):
            # Compare message lists and return only new messages
            last_len = len(self.last_observation)
            if len(current_observation) > last_len:
                # Return only the new messages
                return current_observation[last_len:]
            else:
                # No new messages, return empty list
                return []
        
        # If both are strings, find new text
        elif isinstance(current_observation, str) and isinstance(self.last_observation, str):
            # If current starts with last, return the suffix
            if current_observation.startswith(self.last_observation):
                return current_observation[len(self.last_observation):]
            else:
                # Different content, return current (safer to return all)
                return current_observation
        
        # Mixed types or other cases, return current observation
        else:
            return current_observation
    
    def get_observations(self, timeout: float = 600.0, poll_interval: float = 1.0) -> str:
        """
        Get the current observation/question from the workspace/server.
        
        This retrieves the latest pending question from the interactive API service,
        which was sent by the workspace/server. This method will wait until an
        observation is available.
        
        Args:
            timeout: Maximum time to wait for observation (in seconds). Default: 3600 (1 hour)
            poll_interval: Interval between polling attempts (in seconds). Default: 1.0
        
        Returns:
            Observation string (the question/message from workspace)
        """
        import urllib.request
        import time
        
        start_time = time.time()
        
        while True:
            try:
                # Get observation from interactive API
                # Use longer timeout to avoid connection issues
                with urllib.request.urlopen(
                    f"{self.interactive_api_url}/observation", timeout=10
                ) as resp:
                    data = json.loads(resp.read().decode())
                    has_pending = data.get("has_pending", False)
                    observation = data.get("observation", [])
                    
                    # If there's a pending observation, save request_id and return delta
                    # Check has_pending first, then check if observation is not the default "no pending" message
                    if has_pending:
                        # Save the request_id for use in step()
                        request_id = data.get("request_id")
                        if request_id:
                            self.current_request_id = request_id
                        
                        # Calculate delta: new observation minus last observation
                        delta_observation = self._calculate_observation_delta(observation)
                        
                        # Save current observation as last_observation for next time
                        self.last_observation = observation
                        
                        # Return delta (new messages only)
                        return delta_observation
                    
                    # Check timeout
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return f"Timeout waiting for observation after {timeout} seconds"
                    
                    # Wait before next poll
                    time.sleep(poll_interval)
                    
            except urllib.error.URLError as e:
                # If connection error, wait and retry
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return f"Timeout waiting for observation: {e}"
                time.sleep(poll_interval)
            except Exception as e:
                # For other errors, return error message
                import traceback
                traceback.print_exc()
                raise ValueError(f"Error getting observations: {e}")
    
    def step(self, fn_call: Dict[str, Any]) -> str:
        """
        Submit human response to the current pending request.
        
        This method uses the request_id obtained from the last get_observations() call
        to submit the response from fn_call.
        
        Args:
            fn_call: Dictionary containing the step/action to execute. This can be:
                - Tool call format: {"name": "tool_name", "arguments": {...}}
                - Direct response: {"response": "human's answer"}
                - Any other format will be converted to JSON string
        
        Returns:
            Result string confirming the response was submitted, or error message
        """
        print(f"step: {fn_call}")
        import urllib.request
        
        # Use the request_id from the last get_observations() call
        request_id = self.current_request_id
        
        if not request_id:
            # raise an error
            raise ValueError("No request_id found. Please call get_observations() first.")
        
        # Convert fn_call to response format
        # If it's a tool call, format it appropriately
        if "name" in fn_call and "arguments" in fn_call:
            # Tool call format - convert to a readable response
            tool_name = fn_call["name"]
            tool_args = fn_call["arguments"]
            # Convert arguments to JSON string if it's a dict
            if isinstance(tool_args, dict):
                arguments_str = json.dumps(tool_args)
            elif isinstance(tool_args, str):
                arguments_str = tool_args
            else:
                arguments_str = json.dumps(tool_args)
            
            # Increment counter and use it for tool call ID
            self.tool_call_counter += 1
            tool_call_json = {
                "id": str(self.tool_call_counter),
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments_str
                }
            }
        else:
            tool_call_json = None
        
        if "response" in fn_call:
            human_response = fn_call["response"]

        # Submit response to the most recent request
        try:
            submit_data = {
                "request_id": request_id,
                "response": human_response,
            }
            if tool_call_json is not None:
                submit_data["tool_calls"] = [tool_call_json]
            print(submit_data)
            data = json.dumps(submit_data).encode('utf-8')
            req = urllib.request.Request(
                f"{self.interactive_api_url}/submit_response",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                if result.get("success", False):
                    print(f"Response submitted successfully to request {request_id}")
                else:
                    print(f"Failed to submit response: {result.get('error', 'Unknown error')}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else "No error details"
            print(f"HTTP error submitting response: {e.code} - {error_body}")
        except Exception as e:
            print(f"Error submitting response: {e}")

        return self.get_observations()

    def get_reward(self, **kwargs: Any) -> float:
        """
        Get the current reward for the environment.
        
        In interactive mode, this is a placeholder that returns 0.0.
        The actual reward would be computed by the workspace/server.
        """
        return 0.0
    
    def get_llm_config_path(self) -> str:
        """Get the path to the LLM config file pointing to interactive service.
        
        Returns:
            Path to LLM config JSON file that can be used with test_single_task
        """
        if self.llm_config_path is None:
            raise RuntimeError("Interactive API service not started")
        return self.llm_config_path
    
    def close(self) -> None:
        """Cleanup interactive API service and temporary files."""
        # Check for pending chat-completion requests and submit empty responses
        if self.interactive_api_process is not None:
            try:
                # Check status to see if there are pending requests
                import urllib.request
                status_url = f"{self.interactive_api_url}/status"
                
                # Loop until no pending requests remain
                max_iterations = 10  # Maximum number of iterations to avoid infinite loop
                iteration = 0
                
                while iteration < max_iterations:
                    try:
                        with urllib.request.urlopen(status_url, timeout=2) as resp:
                            status_data = json.loads(resp.read().decode())
                            pending_count = status_data.get("pending_requests", 0)
                            pending_request_ids = status_data.get("pending_request_ids", [])
                            
                            if pending_count == 0:
                                print(f"[Close] No pending requests remaining.", flush=True)
                                break
                            
                            print(f"[Close] Found {pending_count} pending chat-completion request(s), submitting empty responses...", flush=True)
                            
                            # Submit finish action for each pending request
                            for request_id in pending_request_ids:
                                try:
                                    # Create finish tool call
                                    finish_tool_call = {
                                        "id": "0",
                                        "type": "function",
                                        "function": {
                                            "name": "finish",
                                            "arguments": json.dumps({"message": "[closed] Environment is closing. Task terminated."})
                                        }
                                    }
                                    
                                    submit_data = {
                                        "request_id": request_id,
                                        "response": "",  # Empty response text
                                        "tool_calls": [finish_tool_call]  # Finish action
                                    }
                                    data = json.dumps(submit_data).encode('utf-8')
                                    req = urllib.request.Request(
                                        f"{self.interactive_api_url}/submit_response",
                                        data=data,
                                        headers={'Content-Type': 'application/json'}
                                    )
                                    with urllib.request.urlopen(req, timeout=5) as submit_resp:
                                        result = json.loads(submit_resp.read().decode())
                                        if result.get("success", False):
                                            print(f"[Close] Submitted finish action for request {request_id}", flush=True)
                                        else:
                                            print(f"[Close] Failed to submit finish action for {request_id}: {result.get('error', 'Unknown error')}", flush=True)
                                except Exception as e:
                                    print(f"[Close] Error submitting finish action for {request_id}: {e}", flush=True)
                            
                            # Wait 2 seconds before checking again
                            print(f"[Close] Waiting 2 seconds before checking again...", flush=True)
                            time.sleep(2)
                            iteration += 1
                            
                    except Exception as e:
                        print(f"[Close] Could not check pending requests status: {e}", flush=True)
                        break
                
                if iteration >= max_iterations:
                    print(f"[Close] Reached maximum iterations ({max_iterations}), stopping check loop.", flush=True)
                
                # Now stop the interactive API service
                self.interactive_api_process.terminate()
                self.interactive_api_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.interactive_api_process.kill()
            except Exception as e:
                print(f"Error stopping interactive API service: {e}")
            finally:
                self.interactive_api_process = None
        
        # Clean up temporary LLM config file
        if self.llm_config_path and os.path.exists(self.llm_config_path):
            try:
                os.unlink(self.llm_config_path)
            except Exception as e:
                print(f"Error removing temporary LLM config file: {e}")
            finally:
                self.llm_config_path = None
