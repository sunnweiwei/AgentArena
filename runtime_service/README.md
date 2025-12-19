# Runtime Environment Service

A general, efficient API service for managing runtime environments with a string-based JSON interface and dynamic module loading. This service supports multiple environment types simultaneously, making it highly flexible and extensible.

## Features

- **Dynamic Module Loading**: Supports multiple environment types via registry
- **String-based JSON API**: All parameters and responses use JSON strings for maximum flexibility
- **Multi-Environment Support**: Run different environment types in parallel
- **RESTful API**: Clean FastAPI-based REST endpoints
- **Thread-safe**: Uses RLock for concurrent request handling
- **Resource Management**: Automatic cleanup on shutdown
- **UUID-based**: Unique runtime IDs for each environment
- **Pluggable Environments**: Register new environment types in the registry

## Architecture

### Environment Module Interface

Any environment module must provide these functions:

```python
# Meta information about the environment
meta_info = "Description of your environment"

def create_env(**params) -> tuple[env, str]:
    """
    Create environment from params.
    Returns (env_object, meta_info_json_string)
    """
    pass

def env_step(env, params: dict) -> str:
    """
    Execute a step in the environment.
    Returns result as string or dict (will be converted to JSON string)
    """
    pass

def get_reward(env, **kwargs) -> float:
    """
    Calculate and return reward from environment.
    Returns float reward value.
    """
    pass
```

### Environment Module Registry

The server uses a registry system to support multiple environment types. Register new environments in `main.py:14-19`:

```python
ENV_MODULE_REGISTRY = {
    'tau': 'tau_bench',      # Built-in tau-bench environment
    'custom': 'custom_env',  # Your custom environment
    'game': 'game_env',      # Another custom environment
}
```

Each environment type gets a unique key (e.g., `'tau'`) that maps to a Python module name.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Running the Service

```bash
# Option 1: Using the start script
./start_server.sh

# Option 2: Direct Python execution
python main.py

# Option 3: Using uvicorn with custom settings
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

The service will start on `http://0.0.0.0:8001`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

## API Endpoints

### 1. Create Environment

**POST** `/create`

Creates a new runtime environment and returns a unique runtime_id and meta_info.

**Request Body:**
```json
{
  "env_type": "tau",
  "params": "{\"env_name\": \"airline\", \"task_index\": 0}"
}
```

**Response:**
```json
{
  "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
  "meta_info": "{\"initial_question\": \"...\", \"task_info\": {...}, \"tools_info\": [...], \"wiki\": \"...\"}"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/create" \
  -H "Content-Type: application/json" \
  -d '{
    "env_type": "tau",
    "params": "{\"env_name\": \"airline\", \"task_index\": 0}"
  }'
```

**Python Example:**
```python
import requests
import json

params = {
    "env_name": "airline",
    "task_index": 0
}

response = requests.post(
    "http://localhost:8001/create",
    json={
        "env_type": "tau",
        "params": json.dumps(params)
    }
)

result = response.json()
runtime_id = result["runtime_id"]
meta_info = json.loads(result["meta_info"])
```

### 2. Step Environment

**POST** `/step`

Execute an action in the environment and get the result.

**Request Body:**
```json
{
  "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
  "params": "{\"name\": \"search_direct_flight\", \"arguments\": {\"departure_airport\": \"JFK\", \"arrival_airport\": \"LAX\"}}"
}
```

**Response:**
```json
{
  "result": "Flight found: AA123 from JFK to LAX at 10:00 AM"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/step" \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
    "params": "{\"name\": \"search_direct_flight\", \"arguments\": {\"departure_airport\": \"JFK\", \"arrival_airport\": \"LAX\"}}"
  }'
```

**Python Example:**
```python
import requests
import json

step_params = {
    "name": "search_direct_flight",
    "arguments": {
        "departure_airport": "JFK",
        "arrival_airport": "LAX"
    }
}

response = requests.post(
    "http://localhost:8001/step",
    json={
        "runtime_id": runtime_id,
        "params": json.dumps(step_params)
    }
)

result = response.json()["result"]
```

### 3. Get Reward

**POST** `/reward`

Calculate and return the reward from the environment.

**Request Body:**
```json
{
  "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
  "params": "{}"
}
```

**Response:**
```json
{
  "reward": 0.85
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/reward" \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_id": "550e8400-e29b-41d4-a716-446655440000",
    "params": "{}"
  }'
```

**Python Example:**
```python
import requests

response = requests.post(
    "http://localhost:8001/reward",
    json={
        "runtime_id": runtime_id,
        "params": "{}"
    }
)

reward = response.json()["reward"]
print(f"Current reward: {reward}")
```

### 4. Stop Environment

**POST** `/stop`

Stop and cleanup a runtime environment.

**Request Body:**
```json
{
  "runtime_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Environment 550e8400-e29b-41d4-a716-446655440000 stopped successfully"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "runtime_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

### 5. Health Check

**GET** `/health`

Check service health, active environment count, and available environment types.

**Response:**
```json
{
  "status": "healthy",
  "active_environments": 3,
  "available_env_types": ["tau"]
}
```

**Example:**
```bash
curl http://localhost:8001/health
```

### 6. List Environments

**GET** `/environments`

List all active runtime environments with their metadata.

**Response:**
```json
{
  "count": 2,
  "environments": {
    "550e8400-e29b-41d4-a716-446655440000": {
      "env_type": "tau",
      "params": {"env_name": "airline", "task_index": 0},
      "has_meta_info": true
    },
    "660e8400-e29b-41d4-a716-446655440001": {
      "env_type": "tau",
      "params": {"env_name": "retail", "task_index": 1},
      "has_meta_info": true
    }
  }
}
```

**Example:**
```bash
curl http://localhost:8001/environments
```

### 7. List Environment Types

**GET** `/env-types`

List all available environment types with their metadata and availability status.

**Response:**
```json
{
  "env_types": {
    "tau": {
      "module": "tau_bench",
      "meta_info": "Tau-bench environment for airline and retail customer service tasks",
      "available": true
    },
    "custom": {
      "module": "custom_env",
      "meta_info": "Module not available: No module named 'custom_env'",
      "available": false
    }
  }
}
```

**Example:**
```bash
curl http://localhost:8001/env-types
```

## Complete Python Client Example

```python
import requests
import json

class RuntimeClient:
    def __init__(self, base_url="http://localhost:8001", env_type="tau"):
        self.base_url = base_url
        self.env_type = env_type
        self.runtime_id = None

    def create(self, **params):
        """Create a new environment"""
        response = requests.post(
            f"{self.base_url}/create",
            json={
                "env_type": self.env_type,
                "params": json.dumps(params)
            }
        )
        response.raise_for_status()

        result = response.json()
        self.runtime_id = result["runtime_id"]
        meta_info = json.loads(result["meta_info"])

        return self.runtime_id, meta_info

    def step(self, **params):
        """Execute a step"""
        if not self.runtime_id:
            raise ValueError("No active environment. Call create() first.")

        response = requests.post(
            f"{self.base_url}/step",
            json={
                "runtime_id": self.runtime_id,
                "params": json.dumps(params)
            }
        )
        response.raise_for_status()

        return response.json()["result"]

    def get_reward(self, **params):
        """Get current reward"""
        if not self.runtime_id:
            raise ValueError("No active environment. Call create() first.")

        response = requests.post(
            f"{self.base_url}/reward",
            json={
                "runtime_id": self.runtime_id,
                "params": json.dumps(params)
            }
        )
        response.raise_for_status()

        return response.json()["reward"]

    def stop(self):
        """Stop the environment"""
        if not self.runtime_id:
            return

        response = requests.post(
            f"{self.base_url}/stop",
            json={"runtime_id": self.runtime_id}
        )
        response.raise_for_status()

        self.runtime_id = None
        return response.json()

# Usage example
if __name__ == "__main__":
    client = RuntimeClient()

    # Create environment
    runtime_id, meta_info = client.create(env_name="airline", task_index=0)
    print(f"Created environment: {runtime_id}")
    print(f"Initial question: {meta_info['initial_question']}")

    # Execute a step
    result = client.step(
        name="search_direct_flight",
        arguments={
            "departure_airport": "JFK",
            "arrival_airport": "LAX"
        }
    )
    print(f"Step result: {result}")

    # Get reward
    reward = client.get_reward()
    print(f"Reward: {reward}")

    # Stop environment
    client.stop()
    print("Environment stopped")
```

## RuntimeManager Class

The `RuntimeManager` class handles all environment lifecycle operations:

- **Thread Safety**: Uses `threading.RLock()` for concurrent access
- **Environment Storage**: In-memory dictionary indexed by UUID
- **Automatic Cleanup**: Lifespan context manager ensures cleanup on shutdown
- **Module Injection**: Takes environment module as constructor parameter

## Efficiency Features

1. **Thread-safe Operations**: RLock ensures safe concurrent access
2. **String-based Interface**: Minimal serialization overhead with direct JSON strings
3. **Resource Pooling**: Environments stored in memory for fast access
4. **Automatic Cleanup**: Graceful shutdown cleanup of all environments
5. **FastAPI Async**: Async endpoints for better concurrency
6. **Minimal Locking**: Lock only critical sections
7. **General Design**: No environment-specific code in main.py

## Error Handling

- **400 Bad Request**: Invalid JSON in params
- **404 Not Found**: Runtime ID doesn't exist
- **500 Internal Server Error**: Environment creation/step/reward failures

## Creating Custom Environment Modules

To create a custom environment module:

1. Create a new Python file (e.g., `my_env.py`)
2. Implement the required interface:

```python
import json

meta_info = "My custom environment"

def create_env(**params):
    """Create your environment"""
    # Your environment creation logic
    env = MyEnv(**params)

    # Return metadata as JSON string
    meta_data = {
        "initial_state": env.get_state(),
        "config": params
    }

    return env, json.dumps(meta_data)

def env_step(env, params):
    """Execute a step"""
    # Your step logic
    action = params.get('action')
    result = env.execute(action)

    # Return result (string or dict)
    return result

def get_reward(env, **kwargs):
    """Calculate reward"""
    return env.calculate_reward()
```

3. Register your module in the `ENV_MODULE_REGISTRY` in `main.py:14-19`:
```python
ENV_MODULE_REGISTRY = {
    'tau': 'tau_bench',
    'myenv': 'my_env',  # Add your environment here
}
```

4. Use your environment via the API:
```python
client = RuntimeClient(env_type="myenv")
runtime_id, meta_info = client.create(param1="value1", param2="value2")
```

## Development

### Running Tests

```bash
# Add your tests here
pytest tests/
```

### Code Structure

```
runtime_service/
├── main.py              # General API server and RuntimeManager
├── tau_bench.py         # Tau-bench environment module (example)
├── requirements.txt     # Python dependencies
├── start_server.sh      # Start script
└── README.md           # This file
```

## Production Deployment

For production, consider:

1. **Process Manager**: Use PM2 or systemd
2. **Reverse Proxy**: NGINX for SSL and load balancing
3. **Database**: For persistent environment storage
4. **Authentication**: Add API key/JWT authentication
5. **Rate Limiting**: Prevent abuse
6. **Monitoring**: Add logging and metrics (Prometheus/Grafana)
7. **Horizontal Scaling**: Use Redis for shared runtime state

### Example with Gunicorn

```bash
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001
```

## Why String-based JSON Interface?

The string-based JSON interface provides several advantages:

1. **Flexibility**: Any environment can define its own parameter structure
2. **No Schema Lock-in**: No need to update Pydantic models for new environments
3. **Language Agnostic**: Easy to call from any language that supports HTTP and JSON
4. **Future Proof**: New parameters don't require API changes
5. **Simple Serialization**: Direct JSON string passing with minimal overhead

## License

[Your License Here]