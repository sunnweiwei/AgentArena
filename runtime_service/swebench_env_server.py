#!/usr/bin/env python3
"""
Server for managing a pool of SweBenchInteractiveEnv instances.

This server provides:
- POST /create_env: Create a new environment and return a session_id
- POST /close_env/{session_id}: Close and cleanup an environment
- POST /get_observations/{session_id}: Get observations from an environment
- POST /env_step/{session_id}: Execute a step in an environment
- POST /get_reward/{session_id}: Get reward from an environment
- GET /health: Health check
"""

import os
import json
import uuid
import threading
import argparse
import signal
import sys
from typing import Dict, Optional, Any
from pathlib import Path

# Add parent directory to path to allow imports when running as script
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Try relative import first (when used as module), fallback to absolute (when run as script)
try:
    from .swebench_env_impl.core import SweBenchInteractiveEnv
except ImportError:
    from runtime_service.swebench_env_impl.core import SweBenchInteractiveEnv

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class EnvPool:
    """Thread-safe pool for managing SweBenchInteractiveEnv instances."""
    
    def __init__(self, port_pool_base: int = 24123, port_pool_size: int = 100):
        """
        Initialize the environment pool with a port pool.
        
        Args:
            port_pool_base: Base port number for the pool (default: 24123)
            port_pool_size: Size of the port pool (default: 100)
        """
        self._envs: Dict[str, SweBenchInteractiveEnv] = {}
        self._lock = threading.Lock()
        
        # Port pool management
        self.port_pool_base = port_pool_base
        self.port_pool_size = port_pool_size
        self.port_pool_end = port_pool_base + port_pool_size
        # Track which ports are in use: {port: session_id}
        self._ports_in_use: Dict[int, str] = {}
        # Track which session uses which port: {session_id: port}
        self._session_to_port: Dict[str, int] = {}
    
    def _allocate_port(self, requested_port: Optional[int] = None) -> int:
        """
        Allocate a port from the pool.
        
        Args:
            requested_port: Optional specific port to use. If provided and outside pool range,
                          it will be used directly without pool management.
        
        Returns:
            Allocated port number
        
        Raises:
            RuntimeError: If no port is available in the pool
        """
        with self._lock:
            # If port is specified and outside pool range, use it directly
            if requested_port is not None:
                if requested_port < self.port_pool_base or requested_port >= self.port_pool_end:
                    # Port outside pool range - use it directly without tracking
                    return requested_port
                # Port in pool range - check if available
                if requested_port in self._ports_in_use:
                    raise RuntimeError(f"Port {requested_port} is already in use")
                # Allocate the requested port from pool
                return requested_port
            
            # No port specified - allocate from pool (use smallest available)
            for port in range(self.port_pool_base, self.port_pool_end):
                if port not in self._ports_in_use:
                    return port
            
            # No available port
            raise RuntimeError(
                f"No available port in pool range [{self.port_pool_base}, {self.port_pool_end}). "
                f"All {self.port_pool_size} ports are in use."
            )
    
    def _release_port(self, port: int, session_id: str):
        """Release a port back to the pool."""
        with self._lock:
            # Only release if port is in pool range
            if self.port_pool_base <= port < self.port_pool_end:
                if port in self._ports_in_use and self._ports_in_use[port] == session_id:
                    del self._ports_in_use[port]
                if session_id in self._session_to_port:
                    del self._session_to_port[session_id]
    
    def create_env(
        self,
        dataset_name: str = "princeton-nlp/SWE-bench_Verified",
        split: str = "test",
        instance_id: Optional[str] = None,
        instance_index: Optional[int] = None,
        interactive_api_port: Optional[int] = None,
    ) -> str:
        """Create a new environment and return its session_id."""
        session_id = str(uuid.uuid4())
        
        try:
            # Allocate port from pool if not specified
            allocated_port = self._allocate_port(interactive_api_port)
            
            # Track port usage if in pool range
            with self._lock:
                if self.port_pool_base <= allocated_port < self.port_pool_end:
                    self._ports_in_use[allocated_port] = session_id
                    self._session_to_port[session_id] = allocated_port
            
            env_kwargs = {
                "dataset_name": dataset_name,
                "split": split,
                "instance_id": instance_id,
                "instance_index": instance_index,
                "interactive_api_port": allocated_port,
            }
            env = SweBenchInteractiveEnv(**env_kwargs)
            
            with self._lock:
                self._envs[session_id] = env
            
            return session_id
        except Exception as e:
            # If environment creation fails, release the port
            if session_id in self._session_to_port:
                port = self._session_to_port[session_id]
                self._release_port(port, session_id)
            raise RuntimeError(f"Failed to create environment: {e}")
    
    def get_env(self, session_id: str) -> SweBenchInteractiveEnv:
        """Get an environment by session_id."""
        with self._lock:
            if session_id not in self._envs:
                raise ValueError(f"Environment with session_id {session_id} not found")
            return self._envs[session_id]
    
    def close_env(self, session_id: str) -> float:
        """Close and cleanup an environment."""
        with self._lock:
            if session_id not in self._envs:
                raise ValueError(f"Environment with session_id {session_id} not found")
            
            env = self._envs.pop(session_id)
            # Get port before releasing
            port = self._session_to_port.get(session_id)
        
        # Close outside the lock to avoid blocking
        try:
            reward = env.close()
            # Release port after closing
            if port is not None:
                self._release_port(port, session_id)
            return reward
        except Exception as e:
            print(f"Error closing environment {session_id}: {e}")
            # Still release port even if close failed
            if port is not None:
                self._release_port(port, session_id)
            return 0.0
    
    def list_envs(self) -> list:
        """List all active session_ids."""
        with self._lock:
            return list(self._envs.keys())
    
    def get_env_info(self, session_id: str) -> dict:
        """Get information about an environment."""
        env = self.get_env(session_id)
        port = self._session_to_port.get(session_id)
        return {
            "session_id": session_id,
            "dataset_name": env.dataset_name,
            "split": env.split,
            "instance_id": env.instance_id,
            "interactive_api_url": env.interactive_api_url,
            "interactive_api_port": port,
        }
    
    def get_port_pool_stats(self) -> dict:
        """Get statistics about the port pool."""
        with self._lock:
            available_ports = self.port_pool_size - len(self._ports_in_use)
            return {
                "port_pool_base": self.port_pool_base,
                "port_pool_size": self.port_pool_size,
                "port_pool_end": self.port_pool_end,
                "ports_in_use": len(self._ports_in_use),
                "ports_available": available_ports,
            }


# Global environment pool
# Port pool configuration from environment variables or defaults
PORT_POOL_BASE = int(os.getenv("SWEBENCH_PORT_POOL_BASE", "24123"))
PORT_POOL_SIZE = int(os.getenv("SWEBENCH_PORT_POOL_SIZE", "100"))
# Initialize with default values, will be reinitialized in main if needed
env_pool = EnvPool(port_pool_base=PORT_POOL_BASE, port_pool_size=PORT_POOL_SIZE)

# FastAPI app
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# Request/Response models
class CreateEnvRequest(BaseModel):
    dataset_name: str = "princeton-nlp/SWE-bench_Verified"
    split: str = "test"
    instance_id: Optional[str] = None
    instance_index: Optional[int] = None
    interactive_api_port: Optional[int] = None


class CreateEnvResponse(BaseModel):
    session_id: str
    meta: dict


class EnvStepRequest(BaseModel):
    fn_call: dict


class EnvStepResponse(BaseModel):
    observation: str


class GetObservationsResponse(BaseModel):
    observation: str


class GetRewardResponse(BaseModel):
    reward: float


class CloseEnvResponse(BaseModel):
    reward: float
    success: bool


# API endpoints
@app.post("/create_env", response_model=CreateEnvResponse)
async def create_env_endpoint(request: CreateEnvRequest):
    """Create a new environment and return session_id."""
    try:
        session_id = env_pool.create_env(
            dataset_name=request.dataset_name,
            split=request.split,
            instance_id=request.instance_id,
            instance_index=request.instance_index,
            interactive_api_port=request.interactive_api_port,
        )
        
        env = env_pool.get_env(session_id)
        meta = {
            "env_type": "swebench",
            "dataset_name": env.dataset_name,
            "split": env.split,
            "instance_id": env.instance_id,
            "interactive_api_url": env.interactive_api_url,
        }
        
        return CreateEnvResponse(session_id=session_id, meta=meta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/close_env/{session_id}", response_model=CloseEnvResponse)
async def close_env_endpoint(session_id: str):
    """Close and cleanup an environment."""
    try:
        reward = env_pool.close_env(session_id)
        return CloseEnvResponse(reward=reward, success=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/get_observations/{session_id}", response_model=GetObservationsResponse)
async def get_observations_endpoint(session_id: str):
    """Get observations from an environment."""
    try:
        env = env_pool.get_env(session_id)
        observation = env.get_observations()
        return GetObservationsResponse(observation=json.dumps(observation))
    except ValueError as e:
        import traceback
        traceback.print_exc()
        available_sessions = env_pool.list_envs()
        error_msg = f"Environment with session_id {session_id} not found. Available sessions: {available_sessions}"
        raise HTTPException(status_code=404, detail=error_msg)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error getting observations: {str(e)}")


@app.post("/env_step/{session_id}", response_model=EnvStepResponse)
async def env_step_endpoint(session_id: str, request: EnvStepRequest):
    """Execute a step in an environment."""
    try:
        env = env_pool.get_env(session_id)
        result = env.step(request.fn_call)
        
        # Ensure we always return a JSON string (for RuntimeManager.step)
        if isinstance(result, str):
            observation = result
        elif isinstance(result, list):
            for i in range(len(result)):
                if result[i].get("role", "") != "assistant":
                    observation = json.dumps(result[i:])
                    break
            else:
                observation = json.dumps(result)
        else:
            observation = json.dumps(result)
        
        return EnvStepResponse(observation=observation)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/get_reward/{session_id}", response_model=GetRewardResponse)
async def get_reward_endpoint(session_id: str):
    """Get reward from an environment."""
    try:
        env = env_pool.get_env(session_id)
        reward = env.get_reward()
        return GetRewardResponse(reward=reward)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/env_info/{session_id}")
async def get_env_info_endpoint(session_id: str):
    """Get information about an environment."""
    try:
        info = env_pool.get_env_info(session_id)
        return info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/list_envs")
async def list_envs_endpoint():
    """List all active session_ids."""
    session_ids = env_pool.list_envs()
    return {"session_ids": session_ids, "count": len(session_ids)}


@app.get("/port_pool_stats")
async def port_pool_stats_endpoint():
    """Get port pool statistics."""
    return env_pool.get_port_pool_stats()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    port_stats = env_pool.get_port_pool_stats()
    return {
        "status": "healthy",
        "active_envs": len(env_pool.list_envs()),
        "port_pool": port_stats,
    }


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("Shutting down server...")
    # Close all environments
    session_ids = env_pool.list_envs()
    for session_id in session_ids:
        try:
            env_pool.close_env(session_id)
        except Exception as e:
            print(f"Error closing environment {session_id}: {e}")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SweBench Environment Pool Server")
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8132)
    parser.add_argument('--port-pool-base', type=int, default=None,
                       help='Base port number for port pool (default: 24123 or SWEBENCH_PORT_POOL_BASE env var)')
    parser.add_argument('--port-pool-size', type=int, default=None,
                       help='Size of port pool (default: 100 or SWEBENCH_PORT_POOL_SIZE env var)')
    args = parser.parse_args()

    # Update port pool configuration if provided via command line
    port_pool_base = PORT_POOL_BASE
    port_pool_size = PORT_POOL_SIZE
    if args.port_pool_base is not None:
        port_pool_base = args.port_pool_base
    if args.port_pool_size is not None:
        port_pool_size = args.port_pool_size
    
    # Reinitialize env_pool with configuration if different from defaults
    if port_pool_base != PORT_POOL_BASE or port_pool_size != PORT_POOL_SIZE:
        # Reassign module-level variable
        import sys
        current_module = sys.modules[__name__]
        current_module.env_pool = EnvPool(port_pool_base=port_pool_base, port_pool_size=port_pool_size)
    
    print(f"Starting server with port pool: base={port_pool_base}, size={port_pool_size}, range=[{port_pool_base}, {port_pool_base + port_pool_size})")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run(app, host=args.host, port=args.port, workers=1, access_log=False)

