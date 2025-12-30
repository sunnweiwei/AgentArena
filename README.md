# Chat Server Project

A real-time chat application with WebSocket streaming support, featuring multiple AI agents and runtime environments.

## Architecture Overview

The system consists of five main components:

```
┌─────────────┐
│  Frontend   │ (React, Port 3000)
└──────┬──────┘
       │ WebSocket/HTTP
       │
┌──────▼──────────────────────────────────────────────┐
│  Backend Service (Port 8000)                        │
│  - WebSocket server, SQLite database                │
│  - Routes to Agent Service                          │
└──────┬──────────────────────────────────────────────┘
       │ HTTP
       │
┌──────▼──────────────────────────────────────────────┐
│  Agent Service (Port 8001)                          │
│  - search_agent (default)                           │
│  - tau_agent (\tau)                                 │
│  - bc_agent (\bc)                                   │
└──────┬──────────────────────────────────────────────┘
       │ HTTP
       │
┌──────▼──────────────────────────────────────────────┐
│  Runtime Service (Port 8005)                        │
│  - Manages runtime environments (tau, bc, repo)     │
│  - Provides create/step/reward APIs                 │
│  - Can connect to multiple specific servers         │
└──────┬──────────────────────────────────────────────┘
       │ HTTP
       │
┌──────▼──────────────────────────────────────────────┐
│  Specific Servers (e.g., Port 8010, 8011)           │
│  - BC Server: High-throughput search                │
│  - Repo Server: Code execution and file operations  │
│  - Future: Other specialized servers                │
│  - Each environment type can use different servers  │
└─────────────────────────────────────────────────────┘
```

## Components

### 1. Frontend (Port 3000)
**React + Vite** - User interface, WebSocket client, message rendering

**Key Files:** `frontend/src/components/ChatWindow.jsx`, `MessageInput.jsx`

**Env:** `VITE_BACKEND_WS_URL=ws://localhost:8000`

### 2. Backend (Port 8000)
**FastAPI + SQLite** - WebSocket server, database, routes to Agent Service

**Key Files:** `backend/main.py`

**Env:** `OPENAI_API_KEY`, `AGENT_SERVICE_URL=http://localhost:8001`

### 3. Agent Service (Port 8001)
**FastAPI** - Routes to different agent loops, streams responses

**Agent Types:**
- `search_agent` (default) - General purpose
- `tau_agent` (`\tau`) - Tau-bench environments
- `bc_agent` (`\bc`) - BrowseComp research
- `repo_agent` (`\repo`) - Repository code repair (SWE-bench)

**Key Files:** `agent_service/agent_main.py`, `search_agent.py`, `tau_agent.py`, `bc_agent.py`, `repo_agent.py`

**Env:** `OPENAI_API_KEY`, `RUNTIME_SERVICE_URL=http://localhost:8005`

**Routing:**
```python
if message.startswith('\\tau'): → tau_agent_loop
elif message.startswith('\\bc'): → bc_agent_loop
elif message.startswith('\\repo'): → repo_agent_loop
else: → search_agent_loop
```

### 4. Runtime Service (Port 8005)
**FastAPI** - Manages runtime environments, unified API for environment operations

**Environment Types:**
- `tau` - Tau-bench (airline, retail, etc.)
- `bc` - BrowseComp environment
- `repo` - Repository code repair (SWE-bench)

**Key Endpoints:**
- `POST /create` - Create environment
- `POST /step` - Execute action
- `POST /reward` - Calculate reward
- `GET /health` - Health check

**Key Files:** `runtime_service/runtime_server.py`, `tau_env.py`, `bc_env.py`, `repo_env.py`

**Env:** `OPENAI_API_KEY` (for reward calculation)

**Note:** The Runtime Service can connect to multiple specific servers. Each environment type can use different specialized servers as needed.

### 5. Specific Servers (e.g., BC Server on Port 8010, Repo Server on Port 8011)
**FastAPI** - Specialized servers for specific functionality

**Current Implementation:**
- **BC Server** (Port 8010) - High-throughput semantic search using embeddings
  - Used by `bc_agent` via `bc_env`
  - Endpoints: `POST /search`, `POST /open`
- **Repo Server** (Port 8011) - High-performance bash execution and file viewing
  - Used by `repo_agent` via `repo_env` (RepairEnv)
  - Endpoints: `POST /api/v1/actions/code_act` (execute_bash, str_replace_editor)
  - Provides read-only bash commands and file viewing for repository environments
  - File edits (str_replace, insert, create, undo_edit) are handled locally in RepairEnv
  - Supports SWE-bench dataset instances

**Future:** The architecture supports adding more specific servers. Each environment can connect to different specialized servers as needed.

**Key Files:** `runtime_service/bc_server.py`, `runtime_service/repo_server.py`

**Env:** 
- `LOCAL_SEARCH_URL=http://localhost:8010` (used by bc_env)
- `LOC_IP_ADDRESS=http://localhost:8011` (used by repo_env)
- `BASE_DIR_PATH=/path/to/gym_data` (used by repo_env, defaults to `runtime_service/gym_data`)

## API Communication Flow

### Standard Chat Flow
```
User → Frontend → Backend (WebSocket) → Agent Service → [Agent Loop]
```

### BrowseComp (\bc) Flow
```
1. User types "\bc"
2. Backend → Agent Service → bc_agent_loop
3. bc_agent initializes BCEnv
4. BCEnv.create() → Runtime Service POST /create {env_type: "bc"}
5. Agent generates tool calls (search, open_page)
6. BCEnv.step() → Runtime Service POST /step
   → bc_env.run_action() → BC Server POST /search or /open
7. Agent calls finish tool
8. User types "\reward" → BCEnv.get_reward() → Runtime Service POST /reward
```

### Tau (\tau) Flow
```
1. User types "\tau"
2. Agent Service → tau_agent_loop
3. TauEnv.create() → Runtime Service POST /create {env_type: "tau"}
4. TauEnv.step() → Runtime Service POST /step (executes tau-bench tools)
```

### Repo Flow (`\repo`)
```
1. User types "\repo" or "\repo instance_id:xxx"
2. Agent Service → repo_agent_loop
3. RepairEnv.create() → Runtime Service POST /create {env_type: "repo"}
4. Agent generates tool calls (execute_bash, str_replace_editor)
5. RepairEnv.step() → Runtime Service POST /step
   → repo_env handles edits locally, bash via Repo Server
6. User types "\patch" → generates git diff
7. User types "\reward" → RepairEnv.get_reward()
```

## Quick Start

### 1. Environment Setup

**Backend `.env`:**
```bash
OPENAI_API_KEY=sk-...
AGENT_SERVICE_URL=http://localhost:8001
```

**Agent Service `.env`:**
```bash
OPENAI_API_KEY=sk-...
RUNTIME_SERVICE_URL=http://localhost:8005
```

**Runtime Service `.env`:**
```bash
OPENAI_API_KEY=sk-...
```

**Frontend `.env`:**
```bash
VITE_BACKEND_WS_URL=ws://localhost:8000
```

**Note:** API keys can also be stored in `openaikey` file in project root.

### 2. Installation

**Python Services:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# For each service (backend, agent_service, runtime_service):
cd <service>
uv sync
```

**Frontend:**
```bash
cd frontend
npm install
```

### 3. Running Services

**Start All:**
```bash
./start_all.sh
```

**Start Individually:**

```bash
# Backend
cd backend && uv run --env-file=.env python main.py

# Agent Service
cd agent_service && uv run --env-file=.env python agent_main.py

# Runtime Service
cd runtime_service && export OPENAI_API_KEY=$(cat ../openaikey) && uv run python runtime_server.py

# BC Server (example specific server)
cd runtime_service && python bc_server.py --host 0.0.0.0 --port 8010

# Repo Server
cd runtime_service && python repo_server.py

# Frontend
cd frontend && npm run dev
```

## Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| Frontend | 3000 | HTTP |
| Backend | 8000 | HTTP/WebSocket |
| Agent Service | 8001 | HTTP |
| Runtime Service | 8005 | HTTP |
| BC Server | 8010 | HTTP |
| Repo Server | 8011 | HTTP |

## Key Concepts

### Agent Loops
Each agent has an `agent_loop` that:
- Takes conversation history and meta_info
- Yields streaming chunks (text, tool calls, info)
- Manages tool execution and environment interactions

### BaseEnv
Common interface (`agent_service/utils.py`) for:
- `create()` - Initialize environment via Runtime Service
- `step()` - Execute tool call via Runtime Service
- `get_reward()` - Calculate reward via Runtime Service

### Tool Execution
1. Agent generates tool calls: `<function=search><parameter=query>...</parameter></function>`
2. `extract_fn_call()` parses calls (supports both `<parameter=name>value</parameter>` and `<name>value</name>` formats)
3. `fn_call_to_text()` converts back to standard format
4. `env.step(fn_call)` → Runtime Service `/step` → environment's `run_action()`
5. Returns observation to agent

### Meta Info
String-based metadata format:
```
runtime_id: <uuid>
question: <question>
label_answer: <answer>
predicted_answer: <answer>
```

### Specific Servers Architecture
The Runtime Service is designed to connect to multiple specific servers:
- **BC Server** (Port 8010) - Semantic search for BrowseComp
- **Repo Server** (Port 8011) - Read-only bash and file viewing for SWE-bench
- Each environment type can use different servers as needed
- Servers are independent and can run on different ports/machines

## Deployment

**Server:** `sf.lti.cs.cmu.edu` (user: `weiweis`, path: `/usr1/data/weiweis/chat_server`)

**Restart Services:**
```bash
# Agent Service
fuser -k 8001/tcp && cd agent_service && nohup python3 agent_main.py &

# Runtime Service
fuser -k 8005/tcp && cd runtime_service && export OPENAI_API_KEY=$(cat openaikey) && nohup python3 runtime_server.py &

# BC Server
fuser -k 8010/tcp && cd runtime_service && nohup python3 bc_server.py --port 8010 &

# Repo Server
fuser -k 8011/tcp && cd runtime_service && nohup python3 repo_server.py > /tmp/repo_server.log 2>&1 &
```

## Security Notes

- ✅ `.env` files, `key`, `openaikey` are in `.gitignore`
- ❌ Never commit sensitive files

## Documentation

- `runtime_service/README.md` - Runtime Service details
- `ENV_SETUP.md` - Environment setup guide
- `COMMANDS.md` - Server commands
