import uuid
import json
import asyncio
import time
import inspect
from typing import Dict, Any, Optional, Callable
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager


def load_env_module(env_type: str):
    """
    Load environment module based on env_type.
    Returns the imported module.
    """
    if env_type == 'tau':
        import tau_env
        return tau_env
    elif env_type == 'bc':
        import bc_env
        return bc_env
    elif env_type == 'swebench':
        import swebench_env
        return swebench_env
    elif env_type == 'repo':
        import repo_env
        return repo_env
    elif env_type == 'swe':
        import swebench_env_remote
        return swebench_env_remote
    # Add more elif blocks for other environment types
    # elif env_type == 'custom':
    #     import custom_env
    #     return custom_env
    else:
        raise ValueError(f"Unknown env_type: {env_type}.")


async def call_sync_or_async(func: Callable, *args, **kwargs):
    """
    Helper function to call either sync or async functions.
    - If function is async (coroutine function), await it directly
    - If function is sync, run it in thread pool to avoid blocking
    """
    if inspect.iscoroutinefunction(func):
        # Function is async, await it directly
        return await func(*args, **kwargs)
    else:
        # Function is sync, run in thread pool to avoid blocking event loop
        return await asyncio.to_thread(func, *args, **kwargs)


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

        Supports both async and sync create_env functions.
        Async functions are awaited directly, sync functions run in thread pool.
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

        # Create environment (supports both async and sync)
        env, meta_info = await call_sync_or_async(env_module.create_env, **params)

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

        Supports both async and sync env_step functions.
        Async functions are awaited directly, sync functions run in thread pool.
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

        # Execute step (supports both async and sync)
        result = await call_sync_or_async(env_module.env_step, env, params)

        # Convert result to JSON string if it isn't already
        if isinstance(result, str):
            return result
        else:
            return json.dumps(result)

    async def get_reward(self, runtime_id: str, params_str: str = "{}") -> float:
        """
        Get reward from the environment.
        Returns reward value.

        Supports both async and sync get_reward functions.
        Async functions are awaited directly, sync functions run in thread pool.
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

        # Get reward (supports both async and sync)
        return await call_sync_or_async(env_module.get_reward, env, **params)

    async def ping(self, runtime_id: str) -> dict:
        """
        Ping an environment to check if it's alive.
        Calls env.ping() if available and returns meta_info.

        Supports both async and sync ping methods.
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

        # Call ping (supports both async and sync)
        try:
            result = await call_sync_or_async(env.ping)

            # Convert result to JSON string if it isn't already
            if isinstance(result, str):
                ping_result = result
            else:
                ping_result = json.dumps(result)

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

    async def stop(self, runtime_id: str) -> bool:
        """
        Stop and cleanup environment using env-specific close function.
        Supports both async and sync close functions.
        """
        if runtime_id not in self.environments:
            return False

        # Get environment and module
        env_data = self.environments[runtime_id]
        env = env_data['env']
        env_module = env_data.get('env_module')

        # Try to use env_module's close_env function first
        if env_module and hasattr(env_module, 'close_env'):
            await call_sync_or_async(env_module.close_env, env)
        # Otherwise fall back to env.close() if available
        elif hasattr(env, 'close'):
            await call_sync_or_async(env.close)

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
                    await self.stop(runtime_id)

            except Exception as e:
                print(f"Error in cleanup task: {e}")

    async def cleanup_all(self):
        """
        Cleanup all environments using env-specific close functions.
        Supports both async and sync close functions.
        """
        # Get snapshot of runtime_ids to avoid iteration issues
        runtime_ids = list(self.environments.keys())

        for runtime_id in runtime_ids:
            env_data = self.environments.get(runtime_id)
            if env_data:
                env = env_data['env']
                env_module = env_data.get('env_module')

                # Try to use env_module's close_env function first
                if env_module and hasattr(env_module, 'close_env'):
                    await call_sync_or_async(env_module.close_env, env)
                # Otherwise fall back to env.close() if available
                elif hasattr(env, 'close'):
                    await call_sync_or_async(env.close)

        # Clear all at once
        self.environments.clear()

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
    print(f"Create request: env_type={request.env_type}, params={request.params[:200] if len(request.params) > 200 else request.params}")
    try:
        runtime_id, meta_info = await runtime_manager.create_env(request.env_type, request.params)

        return CreateEnvResponse(
            runtime_id=runtime_id,
            meta_info=meta_info,
        )
    except ValueError as e:
        import traceback
        print(f"ValueError in create_environment: {e!r}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        import traceback
        print(f"ImportError in create_environment: {e!r}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_detail = f"Failed to create environment: {str(e)}"
        print(f"Error in create_environment: {e!r}")
        print(f"Create error type: {type(e).__name__}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_detail)


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
        import traceback
        error_detail = f"Failed to get reward: {str(e)}"
        print(f"Error in get_reward endpoint: {e!r}")
        print(f"Reward error type: {type(e).__name__}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_detail)


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
    Stop and cleanup a runtime environment.
    Supports both async and sync close functions.

    Example:
    {
        "runtime_id": "550e8400-e29b-41d4-a716-446655440000"
    }
    """
    try:
        success = await runtime_manager.stop(request.runtime_id)

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



if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8005,
        log_level="info"
    )
