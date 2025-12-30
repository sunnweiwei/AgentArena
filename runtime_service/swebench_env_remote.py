import json
import os
from typing import Any, Tuple, Optional
import urllib.request

# Meta information about this environment module
meta_info = "Interactive SWE-bench environment (remote, server-managed pool)"

# Server URL for environment pool management
SWEBENCH_ENV_SERVER_URL = os.getenv("SWEBENCH_ENV_SERVER_URL", "http://localhost:8132")


class SweBenchEnvProxy:
    """
    Proxy class that wraps a session_id and delegates all operations to the server.
    
    This allows the existing interface to work without changes while using
    a server-managed environment pool.
    """
    
    def __init__(self, session_id: str, server_url: str = SWEBENCH_ENV_SERVER_URL):
        self.session_id = session_id
        self.server_url = server_url.rstrip('/')
    
    def get_observations(self, timeout: float = 600.0, poll_interval: float = 1.0) -> str:
        """Get observations from the server-managed environment."""
        try:
            req = urllib.request.Request(
                f"{self.server_url}/get_observations/{self.session_id}",
                method="POST",
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
                return data.get("observation", "")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else "No error details"
            raise RuntimeError(f"HTTP error getting observations: {e.code} - {error_body}. Session ID: {self.session_id}, Server URL: {self.server_url}")
        except Exception as e:
            raise RuntimeError(f"Error getting observations: {e}. Session ID: {self.session_id}, Server URL: {self.server_url}")
    
    def step(self, fn_call: dict) -> str:
        """Execute a step in the server-managed environment."""
        try:
            data = json.dumps({"fn_call": fn_call}).encode('utf-8')
            req = urllib.request.Request(
                f"{self.server_url}/env_step/{self.session_id}",
                data=data,
                method="POST",
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
                return result.get("observation", "")
        except Exception as e:
            raise RuntimeError(f"Error executing step: {e}")
    
    def get_reward(self, **kwargs: Any) -> float:
        """Get reward from the server-managed environment."""
        try:
            req = urllib.request.Request(
                f"{self.server_url}/get_reward/{self.session_id}",
                method="POST",
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode())
                return float(data.get("reward", 0.0))
        except Exception as e:
            raise RuntimeError(f"Error getting reward: {e}")
    
    def close(self) -> float:
        """Close the server-managed environment."""
        try:
            req = urllib.request.Request(
                f"{self.server_url}/close_env/{self.session_id}",
                method="POST",
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                return float(data.get("reward", 0.0))
        except Exception as e:
            print(f"Error closing environment: {e}")
            return 0.0
    
    def get_llm_config_path(self) -> str:
        """Get LLM config path from server-managed environment."""
        # This requires getting env info from server
        try:
            req = urllib.request.Request(
                f"{self.server_url}/env_info/{self.session_id}",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                # Note: We can't get the actual config path from server
                # This is a limitation - the server would need to expose this
                raise NotImplementedError("get_llm_config_path not supported in server mode")
        except Exception as e:
            raise RuntimeError(f"Error getting env info: {e}")
    
    @property
    def interactive_api_url(self) -> str:
        """Get interactive API URL from server-managed environment."""
        try:
            req = urllib.request.Request(
                f"{self.server_url}/env_info/{self.session_id}",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return data.get("interactive_api_url", "")
        except Exception as e:
            raise RuntimeError(f"Error getting env info: {e}")


def create_env(
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    instance_id: str | None = None,
    instance_index: int | None = None,
    interactive_api_port: Optional[int] = None,
    server_url: Optional[str] = None,
) -> Tuple[SweBenchEnvProxy, str]:
    """
    Create a SWE-bench interactive environment via server.

    This mirrors the interface used by `runtime_server.load_env_module`:
    - returns (env, meta_info_json_str)
    - meta_info is a JSON string with initial observation + metadata

    Args:
        dataset_name: HF dataset name or local path
        split: dataset split to sample from
        instance_id: optional specific instance_id to load
        instance_index: optional integer index into the split
        interactive_api_port: optional port for interactive API service (defaults to 8055)
        server_url: optional server URL (defaults to SWEBENCH_ENV_SERVER_URL env var or http://localhost:8011)

    NOTE: If both instance_id and instance_index are None, a random instance
    will be picked deterministically based on hash of dataset_name+split.
    """
    if server_url is None:
        server_url = SWEBENCH_ENV_SERVER_URL
    
    server_url = server_url.rstrip('/')
    
    # Create environment via server
    try:
        request_data = {
            "dataset_name": dataset_name,
            "split": split,
            "instance_id": instance_id,
            "instance_index": instance_index,
        }
        if interactive_api_port is not None:
            request_data["interactive_api_port"] = interactive_api_port
        data = json.dumps(request_data).encode('utf-8')
        req = urllib.request.Request(
            f"{server_url}/create_env",
            data=data,
            method="POST",
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=300) as resp:  # 5 minute timeout for env creation
            result = json.loads(resp.read().decode())
            session_id = result.get("session_id")
            meta = result.get("meta", {})
            
            if not session_id:
                raise RuntimeError("Server did not return session_id")
            
            # Create proxy object
            env = SweBenchEnvProxy(session_id, server_url)
            
            return env, json.dumps(meta)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else "No error details"
        raise RuntimeError(f"Server error creating environment: {e.code} - {error_body}")
    except Exception as e:
        raise RuntimeError(f"Error creating environment via server: {e}")


def get_observations(env) -> str:
    """
    Get the current observation/question from the workspace/server.
    
    The workspace sends questions to the interactive API service,
    and this function retrieves them.
    
    Returns:
        Observation string (the question/message from workspace)
    """
    return env.get_observations()


def env_step(env, fn_call: dict) -> str:
    """
    Submit human response to the workspace/server.
    
    This mirrors the tau_env signature:
        env_step(env, fn_call: dict) -> observation_str
    
    fn_call is expected to have the structure:
        {
          "response": "human's answer"  # or
          "name": "<action>",
          "arguments": { ... }
        }
    
    In the interactive setup:
      - Workspace sends question to interactive API service
      - get_observations() retrieves the question
      - Human provides answer via env_step()
      - This function forwards the answer to workspace/server
      - Returns result/confirmation from workspace
    """
    result = env.step(fn_call)
    # Ensure we always return a JSON string (for RuntimeManager.step)
    if isinstance(result, str):
        return result
    elif isinstance(result, list):
        for i in range(len(result)):
            if result[i].get("role", "") != "assistant":
                return json.dumps(result[i:])
        return json.dumps(result)
    else:
        raise ValueError(f"Invalid result type: {type(result)}")

def get_reward(env, **kwargs: Any) -> float:
    """
    Get the current reward for the SWE-bench environment.

    By default this returns a shaped heuristic reward based on whether a
    non-empty git patch exists. It does NOT run the full SWE-bench harness.

    To plug in the official SWE-bench evaluation, implement the hook
    `compute_swebench_reward()` in `swebench_env_impl/core.py`.
    """
    return float(env.get_reward(**kwargs))


def close_env(env) -> None:
    """
    Cleanup for the environment.

    Currently a no-op, but provided to match the `tau_env` pattern and allow
    future resource cleanup (e.g., closing RemoteWorkspace handles).
    """
    reward = env.close()
    return reward

