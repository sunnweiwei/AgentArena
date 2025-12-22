# Chat Server Project

A real-time chat application with WebSocket streaming support.

## Quick Start

### 1. Environment Setup

First, set up your environment variables:

```bash
./setup_env.sh
```

This will create a `.env` file from existing `key` and `openaikey` files, or guide you through manual setup.

See `ENV_SETUP.md` for detailed instructions.

### 2. Development

**Backend:**
```bash
cd backend
uv venv venv  # Create virtual environment with uv
source venv/bin/activate
uv pip install -r requirements.txt  # Install dependencies with uv
python main.py
```

**Note:** This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management. If you don't have uv installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
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

## Important Security Notes

- ✅ `.env` files are in `.gitignore` - never commit them
- ✅ `key` and `openaikey` files are also in `.gitignore`
- ✅ Use `.env.example` as a template (safe to commit)
- ❌ **Never commit** `.env`, `key`, or `openaikey` to git

## Server Details

- **Host**: `sf.lti.cs.cmu.edu`
- **User**: `weiweis`
- **Remote Path**: `/usr1/data/weiweis/chat_server`
- **Backend Port**: `8000`
- **Frontend Port**: `3000`
