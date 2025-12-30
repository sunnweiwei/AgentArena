# SWE-Bench Environment Server

This module provides a server-based environment pool management system for SWE-bench interactive environments. It allows you to create, manage, and interact with multiple SWE-bench environments through a centralized server.

## Overview

The system supports two modes of operation:

1. **Local Mode** (`swebench_env.py`): Directly creates environments without a server
2. **Remote Mode** (`swebench_env_remote.py`): Creates environments through a server-managed pool

## Quick Start

### 1. Start the Server

The server manages a pool of environments and handles port allocation automatically.

#### Basic Usage

```bash
# Start server with default configuration
python runtime_service/swebench_env_server.py --port 8132
```

#### With Custom Port Pool

```bash
# Custom port pool: base port 25000, pool size 50 (ports 25000-25049)
python runtime_service/swebench_env_server.py \
    --port 8132 \
    --port-pool-base 25000 \
    --port-pool-size 50
```

#### Using Environment Variables

```bash
# Set port pool configuration via environment variables
export SWEBENCH_PORT_POOL_BASE=25000
export SWEBENCH_PORT_POOL_SIZE=50
export SWEBENCH_ENV_SERVER_URL=http://localhost:8132

# Start server
python runtime_service/swebench_env_server.py --port 8132
```

#### Server Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--host` | Server host address | `0.0.0.0` |
| `--port` | Server port | `8132` |
| `--port-pool-base` | Base port for environment pool | `24123` (or `SWEBENCH_PORT_POOL_BASE` env var) |
| `--port-pool-size` | Size of port pool | `100` (or `SWEBENCH_PORT_POOL_SIZE` env var) |

**Port Pool Range**: `[port-pool-base, port-pool-base + port-pool-size)`

For example, with default settings:
- Base: `24123`
- Size: `100`
- Range: `[24123, 24223)`

### 2. Create and Use Environments

#### Remote Mode (Recommended for Server-Managed Pool)

```python
import runtime_service.swebench_env_remote as swebench_env_remote

# Create environment via server
env, meta = swebench_env_remote.create_env(
    dataset_name="princeton-nlp/SWE-bench_Verified",
    instance_id="django__django-11333",
    server_url="http://localhost:8132",  # Optional, defaults to env var or localhost:8132
    interactive_api_port=None,  # Optional, will be auto-allocated from pool
)

print(f"Session ID: {env.session_id}")
print(f"Meta: {meta}")

# Get observations
observation = env.get_observations()
print(f"Observation: {observation}")

# Execute a step
result = env.step({"response": "I will read the file first to understand the codebase."})
print(f"Result: {result}")

# Get reward
reward = env.get_reward()
print(f"Reward: {reward}")

# Close environment (releases port back to pool)
env.close()
```

#### Local Mode (Direct Creation)

```python
import runtime_service.swebench_env as swebench_env

# Create environment directly (no server needed)
env, meta = swebench_env.create_env(
    dataset_name="princeton-nlp/SWE-bench_Verified",
    instance_id="django__django-11333",
    interactive_api_port=8055,  # Must specify port manually
)

# Use environment (same API as remote mode)
observation = env.get_observations()
result = env.step({"response": "Hello"})
reward = env.get_reward()
env.close()
```

## Port Pool Management

### Automatic Port Allocation

When creating an environment **without** specifying `interactive_api_port`:

1. Server automatically allocates a port from the pool (starting from the smallest available)
2. Port is tracked and released when environment is closed
3. If pool is exhausted, creation fails with a clear error message

### Manual Port Specification

You can specify a port in two ways:

1. **Port in pool range**: Server checks availability and manages it
   ```python
   env, meta = swebench_env_remote.create_env(
       instance_id="django__django-11333",
       interactive_api_port=24125,  # In pool range [24123, 24223)
   )
   ```

2. **Port outside pool range**: Used directly without pool management
   ```python
   env, meta = swebench_env_remote.create_env(
       instance_id="django__django-11333",
       interactive_api_port=30000,  # Outside pool range, used directly
   )
   ```

## API Endpoints

The server provides the following REST API endpoints:

### Environment Management

- `POST /create_env`: Create a new environment
  ```json
  {
    "dataset_name": "princeton-nlp/SWE-bench_Verified",
    "split": "test",
    "instance_id": "django__django-11333",
    "instance_index": null,
    "interactive_api_port": null
  }
  ```
  Returns: `{"session_id": "...", "meta": {...}}`

- `POST /close_env/{session_id}`: Close and cleanup an environment
  Returns: `{"reward": 0.0, "success": true}`

### Environment Interaction

- `POST /get_observations/{session_id}`: Get observations from environment
  Returns: `{"observation": "..."}`

- `POST /env_step/{session_id}`: Execute a step
  ```json
  {
    "fn_call": {
      "response": "I will read the file first.",
      "name": "terminal",
      "arguments": {"command": "ls -la"}
    }
  }
  ```
  Returns: `{"observation": "..."}`

- `POST /get_reward/{session_id}`: Get reward from environment
  Returns: `{"reward": 0.0}`

### Information and Monitoring

- `GET /env_info/{session_id}`: Get environment information
  Returns: `{"session_id": "...", "dataset_name": "...", "interactive_api_port": 24123, ...}`

- `GET /list_envs`: List all active session IDs
  Returns: `{"session_ids": [...], "count": 5}`

- `GET /port_pool_stats`: Get port pool statistics
  Returns: `{"port_pool_base": 24123, "port_pool_size": 100, "ports_in_use": 5, "ports_available": 95, ...}`

- `GET /health`: Health check with port pool info
  Returns: `{"status": "healthy", "active_envs": 5, "port_pool": {...}}`

## Example: Complete Workflow

```python
import runtime_service.swebench_env_remote as swebench_env_remote

# 1. Create environment (server must be running)
env, meta = swebench_env_remote.create_env(
    dataset_name="princeton-nlp/SWE-bench_Verified",
    instance_id="django__django-11333",
    server_url="http://localhost:8132",
)

print(f"Created environment: {env.session_id}")

# 2. Get initial observation
observation = env.get_observations()
print(f"Initial observation: {observation}")

# 3. Execute steps
result1 = env.step({
    "response": "I will first read the issue description to understand the problem."
})
print(f"Step 1 result: {result1}")

result2 = env.step({
    "response": "Now I'll examine the relevant code files.",
    "name": "read_file",
    "arguments": {"path": "django/core/management/commands/runserver.py"}
})
print(f"Step 2 result: {result2}")

# 4. Get reward
reward = env.get_reward()
print(f"Current reward: {reward}")

# 5. Close environment (releases port back to pool)
final_reward = env.close()
print(f"Final reward: {final_reward}")
```

## Server Management

### Start Server

```bash
# Basic
python runtime_service/swebench_env_server.py --port 8132

# With custom port pool
python runtime_service/swebench_env_server.py \
    --port 8132 \
    --port-pool-base 25000 \
    --port-pool-size 50
```

### Stop Server

```bash
# Graceful shutdown (Ctrl+C or SIGTERM)
# Server will close all environments and release ports

# Or use the kill script
./runtime_service/kill_swebench_server.sh

# Or manually
pkill -f swebench_env_server
```

### Check Server Status

```bash
# Health check
curl http://localhost:8132/health

# Port pool statistics
curl http://localhost:8132/port_pool_stats

# List active environments
curl http://localhost:8132/list_envs
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SWEBENCH_ENV_SERVER_URL` | Server URL for remote mode | `http://localhost:8132` |
| `SWEBENCH_PORT_POOL_BASE` | Base port for port pool | `24123` |
| `SWEBENCH_PORT_POOL_SIZE` | Size of port pool | `100` |
| `INTERACTIVE_API_URL` | Interactive API URL (set by environment) | Auto-generated |

### Port Pool Behavior

- **Default range**: `[24123, 24223)` (100 ports)
- **Allocation**: Smallest available port first
- **Release**: Automatic when environment closes
- **External ports**: Ports outside pool range are used directly without tracking

## Troubleshooting

### Port Already in Use

If you get an error about a port being in use:

1. Check if the port is in the pool range
2. If in pool range, it may be allocated to another environment
3. Check port pool stats: `curl http://localhost:8132/port_pool_stats`
4. List active environments: `curl http://localhost:8132/list_envs`

### No Available Ports

If the port pool is exhausted:

1. Increase pool size: `--port-pool-size 200`
2. Close unused environments
3. Check for leaked environments that weren't properly closed

### Server Connection Errors

If you can't connect to the server:

1. Verify server is running: `curl http://localhost:8132/health`
2. Check server URL: `echo $SWEBENCH_ENV_SERVER_URL`
3. Verify port is correct: Default is `8132`

## Architecture

```
┌─────────────────┐
│  Client Code    │
│  (Python)       │
└────────┬────────┘
         │
         │ HTTP API
         │
┌────────▼─────────────────┐
│  swebench_env_server.py  │
│  - EnvPool               │
│  - Port Pool Management   │
│  - Session Management     │
└────────┬──────────────────┘
         │
         │ Creates & Manages
         │
┌────────▼──────────────────┐
│ SweBenchInteractiveEnv    │
│  - Interactive API        │
│  - Task Execution         │
│  - Observation/Step       │
└───────────────────────────┘
```

## Files

- `swebench_env_server.py`: Server for managing environment pool
- `swebench_env_remote.py`: Client library for remote mode (via server)
- `swebench_env.py`: Client library for local mode (direct creation)
- `core.py`: Core `SweBenchInteractiveEnv` implementation
- `interactive_human_api.py`: Interactive API service for human input
- `load_single_task.py`: Task loading and execution

## See Also

- [SWE-Bench Documentation](https://www.swebench.com/)
- [OpenHands Benchmarks README](../README.md)

