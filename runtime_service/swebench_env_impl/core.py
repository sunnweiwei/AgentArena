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


def create_interactive_llm_config(interactive_api_url: str = "http://localhost:8007") -> dict:
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
    
    This class can be used to start an interactive human API service for solving
    SWE-bench tasks manually. The service will display agent messages and wait
    for human input at each step.
    
    Example:
        # Start interactive environment
        env = SweBenchInteractiveEnv(
            dataset_name="princeton-nlp/SWE-bench_Verified",
            instance_id="django__django-11333",
        )
        
        # Get LLM config pointing to the interactive service
        llm_config_path = env.get_llm_config_path()
        
        # Use with test_single_task
        from benchmarks.swebench.test_single_task import test_single_task
        test_single_task(
            instance_id="django__django-11333",
            llm_config_path=llm_config_path,
        )
        
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
    
    def __post_init__(self) -> None:
        """Initialize interactive environment and start API service."""
        # Start interactive API service
        self.interactive_api_process = _start_interactive_human_api_service(
            port=self.interactive_api_port
        )
        
        # Create LLM config file pointing to interactive service
        interactive_api_url = os.getenv(
            "INTERACTIVE_API_URL", f"http://localhost:{self.interactive_api_port}"
        )
        llm_config_dict = create_interactive_llm_config(interactive_api_url)
        
        # Save to logs directory
        log_folder = Path(__file__).parent / "logs"
        log_folder.mkdir(exist_ok=True)
        
        # Generate a unique filename
        import uuid
        config_filename = f"llm_config_{uuid.uuid4().hex[:8]}.json"
        self.llm_config_path = str(log_folder / config_filename)
        
        with open(self.llm_config_path, 'w') as f:
            json.dump(llm_config_dict, f, indent=2)
    
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
        # Stop interactive API service if running
        if self.interactive_api_process is not None:
            try:
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
