"""
Internal implementation package for the interactive SWE-bench environment.

The public entrypoints used by `runtime_server.RuntimeManager` live in
`swebench_env.py` (create_env / env_step / get_reward / close_env).
This package hides the heavier logic (dataset loading, state tracking, and
optional hooks into SWE-bench evaluation / RemoteWorkspace).
"""

from .core import SweBenchInteractiveEnv

__all__ = ["SweBenchInteractiveEnv"]


