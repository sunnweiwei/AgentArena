import json
from typing import Any, Tuple

from .swebench_env_impl.core import SweBenchInteractiveEnv

# Meta information about this environment module
meta_info = "Interactive SWE-bench environment (problem-centric, repo-aware, no tests by default)"


def create_env(
    dataset_name: str = "princeton-nlp/SWE-bench_Verified",
    split: str = "test",
    instance_id: str | None = None,
    instance_index: int | None = None,
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

    NOTE: If both instance_id and instance_index are None, a random instance
    will be picked deterministically based on hash of dataset_name+split.
    """
    env = SweBenchInteractiveEnv(
        dataset_name=dataset_name,
        split=split,
        instance_id=instance_id,
        instance_index=instance_index,
    )

    meta = {
        "env_type": "swebench",
        "dataset_name": dataset_name,
        "split": split,
        "instance_id": env.instance_id,
        "repo": env.instance["repo"],
        "base_commit": env.instance.get("base_commit"),
        "initial_question": env.initial_question,
        "problem_statement": env.instance.get("problem_statement"),
    }

    return env, json.dumps(meta)


def env_step(env: SweBenchInteractiveEnv, fn_call: dict) -> str:
    """
    Execute a step in the SWE-bench environment.

    This mirrors the tau_env signature:
        env_step(env, fn_call: dict) -> observation_str

    fn_call is expected to have the structure:
        {
          "name": "<tool_name_or_action>",
          "arguments": { ... arbitrary JSON-serializable dict ... }
        }

    In a typical interactive setup:
      - The "observation" for the LLM is `initial_question` + history,
      - The LLM outputs a tool call (same structure as above),
      - The tool call is forwarded here as `fn_call`,
      - This function produces a new textual observation string.

    For now, we keep the implementation simple and focus on wiring; the
    heavy SWE-bench / RemoteWorkspace integration lives in `swebench_env_impl`.
    """
    observation = env.step(fn_call)
    # Ensure we always return a JSON string (for RuntimeManager.step)
    if isinstance(observation, str):
        return observation
    return json.dumps(observation)


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
    env.close()
    return


