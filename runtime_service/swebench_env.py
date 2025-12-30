import json
from typing import Any, Tuple, Optional

# Use absolute import to work when imported as a module
try:
    from swebench_env_impl.core import SweBenchInteractiveEnv
except ImportError:
    # Fallback for when imported from parent directory
    from runtime_service.swebench_env_impl.core import SweBenchInteractiveEnv

# Meta information about this environment module
meta_info = "Interactive SWE-bench environment (problem-centric, repo-aware, no tests by default)"


def create_env(
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    instance_id: str | None = None,
    instance_index: int | None = None,
    interactive_api_port: Optional[int] = None,
) -> Tuple[SweBenchInteractiveEnv, str]:
    """
    Create a SWE-bench interactive environment.

    This mirrors the interface used by `runtime_server.load_env_module`:
    - returns (env, meta_info_json_str)
    - meta_info is a JSON string with initial observation + metadata

    Args:
        dataset_name: HF dataset name or local path
        split: dataset split to sample from
        instance_id: optional specific instance_id to load
        instance_index: optional integer index into the split
        interactive_api_port: optional port for interactive API service (defaults to 8055)

    NOTE: If both instance_id and instance_index are None, a random instance
    will be picked deterministically based on hash of dataset_name+split.
    """
    env_kwargs = {
        "dataset_name": dataset_name,
        "split": split,
        "instance_id": instance_id,
        "instance_index": instance_index,
        "interactive_api_port": interactive_api_port,
    }
    env = SweBenchInteractiveEnv(**env_kwargs)

    meta = {
        "env_type": "swebench",
        "dataset_name": dataset_name,
        "split": split,
        "instance_id": instance_id,
        "interactive_api_url": env.interactive_api_url,
    }

    return env, json.dumps(meta)


def get_observations(env: SweBenchInteractiveEnv) -> str:
    """
    Get the current observation/question from the workspace/server.
    
    The workspace sends questions to the interactive API service,
    and this function retrieves them.
    
    Returns:
        Observation string (the question/message from workspace)
    """
    return env.get_observations()


def env_step(env: SweBenchInteractiveEnv, fn_call: dict) -> str:
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

def get_reward(env: SweBenchInteractiveEnv, **kwargs: Any) -> float:
    """
    Get the current reward for the SWE-bench environment.

    By default this returns a shaped heuristic reward based on whether a
    non-empty git patch exists. It does NOT run the full SWE-bench harness.

    To plug in the official SWE-bench evaluation, implement the hook
    `compute_swebench_reward()` in `swebench_env_impl/core.py`.
    """
    return float(env.get_reward(**kwargs))


def close_env(env: SweBenchInteractiveEnv) -> None:
    """
    Cleanup for the environment.

    Currently a no-op, but provided to match the `tau_env` pattern and allow
    future resource cleanup (e.g., closing RemoteWorkspace handles).
    """
    reward = env.close()
    return reward