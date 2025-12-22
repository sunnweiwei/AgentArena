# Chat Server Project

A real-time chat application with WebSocket streaming support.

## Quick Start

### 1. Environment Setup

Create `.env` files for each service to configure environment variables. **All sensitive configuration should be in `.env` files.**

#### Backend `.env` file

Create `backend/.env`:
```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional: Transcription model (defaults to gpt-4o-transcribe)
TRANSCRIPTION_MODEL=gpt-4o-transcribe

# Optional: Agent service URL (defaults to http://sf.lti.cs.cmu.edu:8001)
AGENT_SERVICE_URL=http://localhost:8001

# Optional: Allowed CORS origins (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:4173
```

**Important:** Use `uv run --env-file=.env` to run the backend, which automatically loads the `.env` file. The backend code also supports `python-dotenv` as a fallback, but `uv run --env-file` is the recommended method.

#### Agent Service `.env` file

Create `agent_service/.env`:
```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional: Tavily API Key (for search functionality)
TAVILY_API_KEY=your-tavily-api-key-here

# Optional: Runtime Service URL (for tau-bench environments)
RUNTIME_SERVICE_URL=http://localhost:8005
```

**Important:** Use `uv run --env-file=.env` to run the agent service, which automatically loads the `.env` file.

#### Frontend `.env` file

Create `frontend/.env`:
```bash
# Backend WebSocket URL (for direct connection, bypasses proxy)
VITE_BACKEND_WS_URL=ws://localhost:8000

# Optional: Backend URL (for Vite proxy configuration)
BACKEND_URL=http://localhost:8000
BACKEND_WS_URL=ws://localhost:8000

# Optional: Enable HTTPS
ENABLE_HTTPS=false
```

#### Root `.env` file (for deployment scripts, optional)

Create `.env` in the project root for deployment:
```bash
# SSH credentials for deployment (optional)
SSH_PASSWORD=your-ssh-password
SERVER_HOST=sf.lti.cs.cmu.edu
SERVER_USER=weiweis
REMOTE_PATH=/usr1/data/weiweis/chat_server
```

### 2. Development

**Quick Start (All Services):**
```bash
# Start all services at once
./start_all.sh

# Stop all services
./stop_all.sh
```

**Individual Services:**

**Backend:**
```bash
cd backend
uv sync  # Install dependencies from pyproject.toml (creates .venv automatically)
uv run --env-file=.env python main.py  # Run with .env file loaded
```

**Agent Service:**
```bash
cd agent_service
uv sync  # Install dependencies from pyproject.toml (creates .venv automatically)
uv run --env-file=.env python agent_main.py  # Run with .env file loaded
```

**Runtime Service:**
```bash
cd runtime_service
uv sync  # Install dependencies from pyproject.toml (creates .venv automatically)
uv run --env-file=.env python runtime_server.py  # Run the runtime service
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Note:** All Python services (backend, agent_service, runtime_service) are now proper `uv` projects with `pyproject.toml` and `uv.lock`. Use `uv sync` to install dependencies. The old `requirements.txt` files have been removed - use `pyproject.toml` instead.

**Note:** This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management. The `uv run --env-file=.env` command automatically:
- Activates the virtual environment
- Loads environment variables from the `.env` file
- Runs the Python script

If you don't have uv installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Deployment

See `COMMANDS.md` for deployment commands, or use:

```bash
python deploy.py
```

## Documentation

- **`ENV_SETUP.md`** - Environment variable setup guide
- **`COMMANDS.md`** - Common server commands (sync, restart, check status)
- **`CONTRIBUTING.md`** - Development and deployment workflow
- **`MIGRATION_NOTES.md`** - Notes on migrating to `.env` files
- **`SYSTEM_OVERVIEW.md`** - System architecture and design

## Environment Variables Reference

### Backend (port 8000)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key (from `backend/.env` file) |
| `TRANSCRIPTION_MODEL` | `gpt-4o-transcribe` | Model for audio transcription |
| `AGENT_SERVICE_URL` | `http://sf.lti.cs.cmu.edu:8001` | URL of the agent service |
| `ALLOWED_ORIGINS` | (auto-detected) | Comma-separated list of allowed CORS origins |

### Agent Service (port 8001)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key (from `agent_service/.env` file) |
| `TAVILY_API_KEY` | (optional) | Tavily API key for search functionality |
| `RUNTIME_SERVICE_URL` | `http://sf.lti.cs.cmu.edu:8005` | URL of the runtime service for tau-bench |

### Frontend (port 3000)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_BACKEND_WS_URL` | (optional) | Direct WebSocket URL to backend (bypasses proxy) |
| `BACKEND_URL` | `http://localhost:8000` | Backend URL for Vite proxy |
| `BACKEND_WS_URL` | `ws://localhost:8000` | Backend WebSocket URL for Vite proxy |
| `ENABLE_HTTPS` | `false` | Enable HTTPS for Vite dev server |

## Important Security Notes

- ✅ `.env` files are in `.gitignore` - never commit them
- ✅ `key`, `openaikey`, and `tavilykey` files are also in `.gitignore`
- ✅ Use `.env.example` as a template (safe to commit)
- ❌ **Never commit** `.env`, `key`, `openaikey`, or `tavilykey` to git

## Server Details

- **Host**: `sf.lti.cs.cmu.edu`
- **User**: `weiweis`
- **Remote Path**: `/usr1/data/weiweis/chat_server`
- **Backend Port**: `8000`
- **Frontend Port**: `3000`
