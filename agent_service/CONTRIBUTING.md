# Agent Service - Setup, Usage & Contribution Guide

## Table of Contents
- [Overview](#overview)
- [Setup](#setup)
- [Usage](#usage)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)

---

## Overview

This is a FastAPI-based coding agent service that integrates **trae-agent** (from ByteDance) to provide AI-powered coding assistance. The service creates isolated workspaces for each session and uses trae-agent's optimized tools for file editing, code execution, and task management.

### Key Features
- **Workspace Isolation**: Each session gets its own isolated workspace
- **Path Mapping**: Agent perceives `/workspace`, but actually works in session-specific directories
- **Trae-Agent Tools**: Uses battle-tested tools (bash, file editing, JSON editing, sequential thinking)
- **Code Execution**: All code runs in the `gpt` conda environment
- **OpenAI Integration**: Powered by OpenAI's GPT models

### Service Endpoints
- **Health Check**: `GET /health`
- **Create Session**: `POST /sessions`
- **Send Task**: `POST /sessions/{session_id}/prompt`

---

## Setup

### Prerequisites
- Python 3.12+ (via conda)
- OpenAI API key
- Access to the server: `sf.lti.cs.cmu.edu`

### Initial Setup

#### 1. Create Conda Environment
```bash
ssh weiweis@sf.lti.cs.cmu.edu
source /usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh
conda create -n agent_py312 python=3.12 -y
conda activate agent_py312
```

#### 2. Clone/Copy the Service
```bash
cd /usr1/data/weiweis/
# The service should be in: /usr1/data/weiweis/agent_service/
```

#### 3. Install Dependencies
```bash
cd /usr1/data/weiweis/agent_service
pip install -r requirements.txt
```

#### 4. Configure API Key
Create a `.env` file in the service directory:
```bash
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

#### 5. Make Start Script Executable
```bash
chmod +x start.sh
```

### Directory Structure
```
/usr1/data/weiweis/agent_service/
├── agent_main.py          # FastAPI application entry point
├── config.py              # Configuration (loads from .env)
├── start.sh               # Startup script (activates conda env)
├── requirements.txt       # Python dependencies
├── .env                   # API keys (not in git)
├── agent/
│   ├── trae_wrapper.py    # Wrapper for trae-agent integration
│   ├── core.py            # Backup: Custom agent implementation
│   └── tools.py           # Backup: Custom tools
├── utils/
│   └── path_mapper.py     # Workspace isolation & path mapping
├── trae_agent/            # Trae-agent codebase (from ByteDance)
│   ├── agent/             # Agent logic
│   ├── tools/             # Optimized tools (bash, edit, json, etc.)
│   └── utils/             # LLM clients, config, etc.
└── workspace/             # Session workspaces (created at runtime)
    └── {session-id}/      # Isolated workspace per session
```

---

## Usage

### Starting the Service

```bash
ssh weiweis@sf.lti.cs.cmu.edu
cd /usr1/data/weiweis/agent_service
./start.sh
```

The service will start on **port 8001**.

### Stopping the Service

```bash
ssh weiweis@sf.lti.cs.cmu.edu
pkill -9 -f agent_main
```

### Checking Service Status

```bash
# Check if service is running
ssh weiweis@sf.lti.cs.cmu.edu "ss -tuln | grep :8001"

# View logs
ssh weiweis@sf.lti.cs.cmu.edu "tail -f /usr1/data/weiweis/agent_service/service.log"
```

### API Usage Examples

#### 1. Health Check
```bash
curl http://sf.lti.cs.cmu.edu:8001/health
```

Response:
```json
{"status": "ok"}
```

#### 2. Create a Session
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions
```

Response:
```json
{
  "session_id": "abc123...",
  "workspace_path": "/usr1/data/weiweis/agent_service/workspace/abc123..."
}
```

#### 3. Send a Task to the Agent
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions/abc123.../prompt \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a Python script that calculates fibonacci numbers and save it as fib.py"
  }'
```

Response:
```json
{
  "response": "I've created the fibonacci script...",
  "history": [...]
}
```

### Example Workflow

```python
import requests

# 1. Create session
response = requests.post("http://sf.lti.cs.cmu.edu:8001/sessions")
session_id = response.json()["session_id"]

# 2. Send task
task = {
    "prompt": "Create a hello world Python script and run it"
}
response = requests.post(
    f"http://sf.lti.cs.cmu.edu:8001/sessions/{session_id}/prompt",
    json=task
)
print(response.json()["response"])
```

---

## Architecture

### Components

#### 1. **agent_main.py** - FastAPI Application
- Handles HTTP requests
- Manages sessions (in-memory storage)
- Routes requests to the agent

#### 2. **agent/trae_wrapper.py** - Trae-Agent Integration
- Wraps trae-agent for our service
- Handles workspace path mapping
- Manages agent initialization and execution

#### 3. **utils/path_mapper.py** - Workspace Isolation
- Maps virtual `/workspace` to real session directories
- Prevents path traversal attacks
- Ensures session isolation

#### 4. **config.py** - Configuration
- Loads environment variables
- Defines service settings (host, port, paths)
- Configures conda environment

#### 5. **trae_agent/** - Trae-Agent Codebase
The core agent from ByteDance with optimized tools:
- **bash**: Execute shell commands
- **str_replace_based_edit_tool**: Advanced file editing
- **json_edit_tool**: JSON file manipulation
- **sequentialthinking**: Task decomposition
- **task_done**: Task completion marker

### Data Flow

```
Client Request
    ↓
FastAPI (agent_main.py)
    ↓
TraeAgentWrapper (agent/trae_wrapper.py)
    ↓
TraeAgent (trae_agent/agent/trae_agent.py)
    ↓
Tools (trae_agent/tools/)
    ↓
Workspace (workspace/{session_id}/)
```

### Workspace Isolation

Each session gets its own isolated workspace:
- **Virtual Path** (what agent sees): `/workspace/file.py`
- **Real Path**: `/usr1/data/weiweis/agent_service/workspace/{session_id}/file.py`

The `PathMapper` class handles translation and security.

---

## Contributing

### Development Workflow

#### 1. Local Development
```bash
# Work on your local machine
cd /Users/sunweiwei/NLP/base_project/agent_service/

# Make changes to files
# Test locally if possible
```

#### 2. Deploy to Server
```bash
# From local machine
scp -r agent_service/* weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/agent_service/

# Or use the deployment scripts
```

#### 3. Restart Service
```bash
ssh weiweis@sf.lti.cs.cmu.edu
pkill -9 -f agent_main
cd /usr1/data/weiweis/agent_service
./start.sh
```

### Adding New Features

#### Adding a New Endpoint

1. Edit `agent_main.py`:
```python
@app.post("/your-endpoint")
async def your_function():
    # Your logic here
    return {"result": "success"}
```

2. Deploy and restart the service

#### Modifying Agent Behavior

1. Edit `agent/trae_wrapper.py`:
```python
class TraeAgentWrapper:
    async def _run_agent(self, task: str):
        # Modify agent configuration
        # Change max_steps, add custom logic, etc.
```

2. Deploy and restart

#### Adding Custom Tools

If you need custom tools beyond trae-agent's:

1. Create tool in `agent/tools.py`
2. Register it in the agent initialization
3. Update the wrapper to use it

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings to functions and classes
- Keep functions focused and small

### Testing

Before deploying:

1. **Test Health Endpoint**:
```bash
curl http://sf.lti.cs.cmu.edu:8001/health
```

2. **Test Session Creation**:
```bash
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions
```

3. **Test Agent Functionality**:
```bash
# Create session, then send a simple task
curl -X POST http://sf.lti.cs.cmu.edu:8001/sessions/{id}/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "List files in current directory"}'
```

### Important Notes

⚠️ **Service Isolation**
- Agent service runs on port **8001**
- Chat server runs on port **8000**
- They are completely isolated
- **Never** modify the chat server when working on agent service

⚠️ **Python Environment**
- Agent service uses `agent_py312` conda environment
- Chat server uses its own `venv`
- Always activate the correct environment

⚠️ **Cache Issues**
If you encounter import errors after updates:
```bash
ssh weiweis@sf.lti.cs.cmu.edu
cd /usr1/data/weiweis/agent_service
find . -type f -name '*.pyc' -delete
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
pkill -9 -f agent_main
./start.sh
```

---

## Troubleshooting

### Service Won't Start

**Check logs**:
```bash
tail -100 /usr1/data/weiweis/agent_service/service.log
```

**Common issues**:
1. **Port already in use**: Another process is using port 8001
   ```bash
   ss -tuln | grep :8001
   pkill -9 -f agent_main
   ```

2. **Missing dependencies**: Install requirements
   ```bash
   conda activate agent_py312
   pip install -r requirements.txt
   ```

3. **API key not set**: Check `.env` file
   ```bash
   cat /usr1/data/weiweis/agent_service/.env
   ```

### Import Errors

**Clear Python cache**:
```bash
cd /usr1/data/weiweis/agent_service
find . -type f -name '*.pyc' -delete
find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
```

### Agent Not Responding

1. **Check if service is running**:
   ```bash
   ss -tuln | grep :8001
   ```

2. **Check logs for errors**:
   ```bash
   tail -50 /usr1/data/weiweis/agent_service/service.log
   ```

3. **Restart service**:
   ```bash
   pkill -9 -f agent_main
   cd /usr1/data/weiweis/agent_service
   ./start.sh
   ```

### Workspace Issues

**Check workspace permissions**:
```bash
ls -la /usr1/data/weiweis/agent_service/workspace/
```

**Clean up old workspaces** (optional):
```bash
# Remove workspaces older than 7 days
find /usr1/data/weiweis/agent_service/workspace/ -type d -mtime +7 -exec rm -rf {} +
```

---

## Dependencies

### Core Dependencies
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `openai` - OpenAI API client
- `pydantic` - Data validation
- `requests` - HTTP client

### Trae-Agent Dependencies
- `anthropic` - Anthropic API support
- `google-generativeai` - Google AI support
- `rich` - Terminal formatting
- `aiofiles` - Async file operations
- `gitpython` - Git operations
- `tree-sitter` - Code parsing
- `jsonpath-ng` - JSON manipulation
- `pyyaml` - YAML parsing
- `textual` - TUI framework
- `mcp` - Model Context Protocol
- `docker` - Docker integration
- `pexpect` - Process control

---

## FAQ

**Q: Can I use a different LLM provider?**
A: Yes! Trae-agent supports multiple providers (OpenAI, Anthropic, Google). Modify `config.py` and `agent/trae_wrapper.py` to change the provider.

**Q: How do I increase the agent's step limit?**
A: Edit `agent/trae_wrapper.py`, change `max_steps` in the `TraeAgentConfig`.

**Q: Can I add custom tools?**
A: Yes! You can either extend trae-agent's tools or create custom ones in `agent/tools.py`.

**Q: How do I monitor agent performance?**
A: Check the logs in `service.log`. You can also add custom logging in the wrapper.

**Q: Is the service production-ready?**
A: It's functional but consider adding:
- Persistent session storage (currently in-memory)
- Authentication/authorization
- Rate limiting
- Better error handling
- Monitoring and metrics

---

## Resources

- **Trae-Agent Repository**: https://github.com/bytedance/trae-agent
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **OpenAI API**: https://platform.openai.com/docs/

---

## License

This service integrates trae-agent which is licensed under MIT License.
See the trae_agent directory for full license information.

---

## Contact

For questions or issues, contact the development team or check the service logs.

**Server**: `sf.lti.cs.cmu.edu`
**Service Directory**: `/usr1/data/weiweis/agent_service`
**Port**: 8001
