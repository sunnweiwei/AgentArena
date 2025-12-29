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
    
    def __init__(self):
        self._envs: Dict[str, SweBenchInteractiveEnv] = {}
        self._lock = threading.Lock()
    
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
            env_kwargs = {
                "dataset_name": dataset_name,
                "split": split,
                "instance_id": instance_id,
                "instance_index": instance_index,
                "interactive_api_port": interactive_api_port,
            }
            env = SweBenchInteractiveEnv(**env_kwargs)
            with self._lock:
                self._envs[session_id] = env
            
            return session_id
        except Exception as e:
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
        
        # Close outside the lock to avoid blocking
        try:
            reward = env.close()
            return reward
        except Exception as e:
            print(f"Error closing environment {session_id}: {e}")
            return 0.0
    
    def list_envs(self) -> list:
        """List all active session_ids."""
        with self._lock:
            return list(self._envs.keys())
    
    def get_env_info(self, session_id: str) -> dict:
        """Get information about an environment."""
        env = self.get_env(session_id)
        return {
            "session_id": session_id,
            "dataset_name": env.dataset_name,
            "split": env.split,
            "instance_id": env.instance_id,
            "interactive_api_url": env.interactive_api_url,
        }


# Global environment pool
env_pool = EnvPool()

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "active_envs": len(env_pool.list_envs())}


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
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    uvicorn.run(app, host=args.host, port=args.port, workers=1, access_log=False)

