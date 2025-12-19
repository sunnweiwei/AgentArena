import uuid
import json
import asyncio
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager


# Environment Module Registry
# Maps env_type to module name
ENV_MODULE_REGISTRY = {
    'tau': 'tau_env',
    # Add more environment types here
    # 'custom': 'custom_env',
    # 'game': 'game_env',
}


def load_env_module(env_type: str):
    """
    Load environment module based on env_type.
    Returns the imported module.
    """
    if env_type == 'tau':
        import tau_env
        return tau_env
    # Add more elif blocks for other environment types
    # elif env_type == 'custom':
    #     import custom_env
    #     return custom_env
    else:
        raise ValueError(f"Unknown env_type: {env_type}. Available types: {list(ENV_MODULE_REGISTRY.keys())}")


# Request/Response Models - All use string-based JSON
class CreateEnvRequest(BaseModel):
    env_type: str  # Type of environment (e.g., 'tau', 'custom')
    params: str  # JSON string of parameters


class CreateEnvResponse(BaseModel):
    runtime_id: str
    meta_info: str  # JSON string with environment metadata


class StepRequest(BaseModel):
    runtime_id: str
    params: str  # JSON string of step parameters


class StepResponse(BaseModel):
    result: str  # JSON string with step result


class RewardRequest(BaseModel):
    runtime_id: str
    params: str = "{}"  # Optional JSON string of reward parameters


class RewardResponse(BaseModel):
    reward: float


class StopRequest(BaseModel):
    runtime_id: str


class StopResponse(BaseModel):
    success: bool
    message: str


class PingRequest(BaseModel):
    runtime_id: str


class PingResponse(BaseModel):
    exists: bool
    has_ping: bool
    ping_result: Optional[str] = None
    meta_info: Optional[str] = None
    message: str


# Runtime Environment Manager
class RuntimeManager:
    def __init__(self):
        self.environments: Dict[str, Any] = {}
        # No locks needed! Dict operations are atomic in CPython (GIL)
        self.idle_timeout = 2 * 60 * 60  # 2 hours in seconds
        self.cleanup_task = None

    async def create_env(self, env_type: str, params_str: str) -> tuple[str, str]:
        """
        Create a new environment from env_type and JSON params string.
        Returns (runtime_id, meta_info_json_string)

        Runs in thread pool to avoid blocking event loop (can take minutes)
        """
        # Generate unique runtime ID
        runtime_id = str(uuid.uuid4())

        # Load environment module based on env_type
        env_module = load_env_module(env_type)

        # Parse parameters
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in params: {e}")

        # Create environment in thread pool (this can be VERY slow - 5+ minutes)
        def _create_env_blocking():
            return env_module.create_env(**params)

        env, meta_info = await asyncio.to_thread(_create_env_blocking)

        # Store environment (dict assignment is atomic in CPython)
        self.environments[runtime_id] = {
            'env': env,
            'env_type': env_type,
            'env_module': env_module,
            'meta_info': meta_info,
            'params': params,
            'last_interaction': time.time(),  # Track interaction time
        }

        return runtime_id, meta_info

    async def step(self, runtime_id: str, params_str: str) -> str:
        """
        Execute a step in the environment.
        Returns JSON string with result.

        Runs in thread pool to avoid blocking event loop (can take 10+ minutes)
        """
        # Quick dict lookup (thread-safe read in CPython)
        env_data = self.environments.get(runtime_id)
        if env_data is None:
            raise ValueError(f"Runtime ID {runtime_id} not found")

        env = env_data['env']
        env_module = env_data['env_module']

        # Update last interaction time
        env_data['last_interaction'] = time.time()

        # Parse step parameters
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in params: {e}")

        # Execute step in thread pool (this can be VERY slow - 10+ minutes)
        # This allows multiple slow steps to run in parallel without blocking!
        def _step_blocking():
            result = env_module.env_step(env, params)
            # Convert result to JSON string if it isn't already
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result)

        return await asyncio.to_thread(_step_blocking)

    async def get_reward(self, runtime_id: str, params_str: str = "{}") -> float:
        """
        Get reward from the environment.
        Returns reward value.

        Runs in thread pool to avoid blocking event loop
        """
        # Quick dict lookup (thread-safe read in CPython)
        env_data = self.environments.get(runtime_id)
        if env_data is None:
            raise ValueError(f"Runtime ID {runtime_id} not found")

        env = env_data['env']
        env_module = env_data['env_module']

        # Update last interaction time
        env_data['last_interaction'] = time.time()

        # Parse reward parameters
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in params: {e}")

        # Get reward in thread pool (can be slow)
        def _get_reward_blocking():
            return env_module.get_reward(env, **params)

        return await asyncio.to_thread(_get_reward_blocking)

    async def ping(self, runtime_id: str) -> dict:
        """
        Ping an environment to check if it's alive.
        Calls env.ping() if available and returns meta_info.
        """
        # Check if runtime exists
        env_data = self.environments.get(runtime_id)
        if env_data is None:
            return {
                'exists': False,
                'has_ping': False,
                'ping_result': None,
                'meta_info': None,
                'message': f"Runtime ID {runtime_id} not found"
            }

        env = env_data['env']
        meta_info = env_data.get('meta_info')

        # Update last interaction time
        env_data['last_interaction'] = time.time()

        # Check if env has ping method
        if not hasattr(env, 'ping'):
            return {
                'exists': True,
                'has_ping': False,
                'ping_result': None,
                'meta_info': meta_info,
                'message': 'Environment exists but has no ping() method'
            }

        # Call ping in thread pool (might be slow)
        def _ping_blocking():
            result = env.ping()
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result)

        try:
            ping_result = await asyncio.to_thread(_ping_blocking)
            return {
                'exists': True,
                'has_ping': True,
                'ping_result': ping_result,
                'meta_info': meta_info,
                'message': 'Ping successful'
            }
        except Exception as e:
            return {
                'exists': True,
                'has_ping': True,
                'ping_result': None,
                'meta_info': meta_info,
                'message': f'Ping failed: {str(e)}'
            }

    def stop(self, runtime_id: str) -> bool:
        """
        Stop and cleanup environment.
        No lock needed - dict operations are atomic in CPython (GIL).
        """
        if runtime_id not in self.environments:
            return False

        # Get environment
        env_data = self.environments[runtime_id]
        env = env_data['env']

        # Cleanup if env has close method
        if hasattr(env, 'close'):
            env.close()

        # Remove from storage (atomic operation in CPython)
        del self.environments[runtime_id]

        return True

    def get_env_data(self, runtime_id: str) -> Optional[Dict[str, Any]]:
        """Get environment data by runtime_id"""
        # No lock needed for read
        return self.environments.get(runtime_id)

    def get_all_envs_snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Get a snapshot of all environments (for listing)"""
        # Make a shallow copy - dict() is atomic enough in CPython
        return dict(self.environments)

    async def cleanup_idle_environments(self):
        """
        Background task that periodically checks for idle environments
        and stops them if they haven't been used for 2 hours.
        """
        while True:
            try:
                # Sleep for 10 minutes between checks
                await asyncio.sleep(10 * 60)

                current_time = time.time()
                idle_environments = []

                # Find idle environments
                for runtime_id, env_data in list(self.environments.items()):
                    last_interaction = env_data.get('last_interaction', current_time)
                    idle_time = current_time - last_interaction

                    if idle_time > self.idle_timeout:
                        idle_environments.append((runtime_id, idle_time))

                # Stop idle environments
                for runtime_id, idle_time in idle_environments:
                    print(f"Auto-stopping idle environment {runtime_id} (idle for {idle_time/3600:.1f} hours)")
                    self.stop(runtime_id)

            except Exception as e:
                print(f"Error in cleanup task: {e}")

    async def cleanup_all(self):
        """Cleanup all environments"""
        def _cleanup_blocking():
            # Get snapshot of runtime_ids to avoid iteration issues
            runtime_ids = list(self.environments.keys())
            for runtime_id in runtime_ids:
                env_data = self.environments.get(runtime_id)
                if env_data:
                    env = env_data['env']
                    if hasattr(env, 'close'):
                        env.close()
            # Clear all at once
            self.environments.clear()

        await asyncio.to_thread(_cleanup_blocking)

    def start_cleanup_task(self):
        """Start the background cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.cleanup_idle_environments())

    def stop_cleanup_task(self):
        """Stop the background cleanup task"""
        if self.cleanup_task:
            self.cleanup_task.cancel()


# Global runtime manager
runtime_manager = RuntimeManager()


# Lifespan context manager for cleanup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - start background cleanup task
    runtime_manager.start_cleanup_task()
    print("Started idle environment cleanup task (checks every 10 minutes, timeout: 2 hours)")
    yield
    # Shutdown - stop cleanup task and cleanup all environments
    runtime_manager.stop_cleanup_task()
    await runtime_manager.cleanup_all()


# FastAPI app
app = FastAPI(
    title="Runtime Environment Service",
    description="General API service for managing runtime environments with dynamic module loading and async execution",
    version="2.0.0",
    lifespan=lifespan
)


@app.post("/create", response_model=CreateEnvResponse)
async def create_environment(request: CreateEnvRequest):
    """
    Create a new runtime environment (async, non-blocking).

    Request includes env_type and params as JSON string.
    Returns runtime_id and meta_info JSON string.

    This operation runs in background thread pool, so multiple
    create requests can run in parallel without blocking.

    Example:
    {
        "env_type": "tau",
        "params": "{\"env_name\": \"airline\", \"task_index\": 0}"
    }
    """
    try:
        runtime_id, meta_info = await runtime_manager.create_env(request.env_type, request.params)

        return CreateEnvResponse(
            runtime_id=runtime_id,
            meta_info=meta_info,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create environment: {str(e)}")


@app.post("/step", response_model=StepResponse)
async def step_environment(request: StepRequest):
    """
    Execute a step in the environment (async, non-blocking).

    Request params is a JSON string with step-specific parameters.
    Returns result as JSON string.

    This operation runs in background thread pool, so multiple
    step requests can run in parallel without blocking.

    Example:
    {
        "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
        "params": "{\"name\": \"search_direct_flight\", \"arguments\": {\"departure_airport\": \"JFK\"}}"
    }
    """
    try:
        result = await runtime_manager.step(request.runtime_id, request.params)

        return StepResponse(result=result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        print(f"Error in step_environment: {e!r}")
        print(f"Step error type: {type(e).__name__}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to execute step: {str(e)}")


@app.post("/reward", response_model=RewardResponse)
async def get_reward(request: RewardRequest):
    """
    Get reward from the environment (async, non-blocking).

    Request params is an optional JSON string with reward-specific parameters.
    Returns reward value.

    This operation runs in background thread pool.

    Example:
    {
        "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
        "params": "{}"
    }
    """
    try:
        reward = await runtime_manager.get_reward(request.runtime_id, request.params)

        return RewardResponse(reward=reward)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reward: {str(e)}")


@app.post("/ping", response_model=PingResponse)
async def ping_environment(request: PingRequest):
    """
    Ping an environment to check if it's alive and responsive.

    Checks if the runtime_id exists and calls env.ping() if available.

    Example:
    {
        "runtime_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """
    try:
        result = await runtime_manager.ping(request.runtime_id)
        return PingResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ping environment: {str(e)}")


@app.post("/stop", response_model=StopResponse)
async def stop_environment(request: StopRequest):
    """
    Stop and cleanup a runtime environment (fast, synchronous).

    Example:
    {
        "runtime_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """
    try:
        success = runtime_manager.stop(request.runtime_id)

        if success:
            return StopResponse(
                success=True,
                message=f"Environment {request.runtime_id} stopped successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Runtime ID {request.runtime_id} not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop environment: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_environments": len(runtime_manager.environments),
        "available_env_types": list(ENV_MODULE_REGISTRY.keys()),
    }


@app.get("/environments")
async def list_environments():
    """List all active runtime environments"""
    envs_snapshot = runtime_manager.get_all_envs_snapshot()
    envs = {}
    for runtime_id, data in envs_snapshot.items():
        envs[runtime_id] = {
            "env_type": data.get('env_type'),
            "params": data.get('params', {}),
            "has_meta_info": bool(data.get('meta_info'))
        }
    return {
        "count": len(envs),
        "environments": envs
    }


@app.get("/env-types")
async def list_env_types():
    """List all available environment types and their metadata"""
    env_types_info = {}

    for env_type in ENV_MODULE_REGISTRY.keys():
        try:
            module = load_env_module(env_type)
            meta_info = getattr(module, 'meta_info', 'No description available')
            env_types_info[env_type] = {
                "module": ENV_MODULE_REGISTRY[env_type],
                "meta_info": meta_info,
                "available": True
            }
        except (ImportError, ValueError) as e:
            env_types_info[env_type] = {
                "module": ENV_MODULE_REGISTRY[env_type],
                "meta_info": f"Module not available: {e}",
                "available": False
            }

    return {
        "env_types": env_types_info
    }


if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8005,
        log_level="info"
    )
