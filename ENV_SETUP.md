# Environment Setup Guide

This project uses `.env` files to store sensitive credentials. **Never commit `.env` files to git!**

## Quick Setup

1. **Run the setup script:**
   ```bash
   ./setup_env.sh
   ```
   
   This will automatically migrate from existing `key` and `openaikey` files if they exist, or guide you through manual setup.

2. **Or manually create `.env`:**
   ```bash
   cp .env.example .env
   # Then edit .env and fill in your credentials
   ```

## Environment Variables

The `.env` file should contain:

```bash
# SSH password for server access
SSH_PASSWORD=your_ssh_password_here

# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Server details (optional - defaults shown)
SERVER_HOST=sf.lti.cs.cmu.edu
SERVER_USER=weiweis
REMOTE_PATH=/usr1/data/weiweis/chat_server
```

## Migration from Legacy Files

If you have existing `key` and `openaikey` files:

1. Run `./setup_env.sh` to automatically migrate
2. Or manually:
   ```bash
   echo "SSH_PASSWORD=$(cat key)" > .env
   echo "OPENAI_API_KEY=$(cat openaikey)" >> .env
   ```

After migration, you can safely delete the old files:
```bash
rm key openaikey
```

## Using Environment Variables

### In Bash/Shell Scripts

```bash
source load_env.sh
# Now $SSH_PASSWORD and $OPENAI_API_KEY are available
```

### In Python Scripts

```python
from dotenv import load_dotenv
import os

load_dotenv()
password = os.getenv('SSH_PASSWORD')
api_key = os.getenv('OPENAI_API_KEY')
```

## Security Notes

- ✅ `.env` is already in `.gitignore` - it will not be committed
- ✅ `key` and `openaikey` files are also in `.gitignore`
- ❌ **Never commit** `.env`, `key`, or `openaikey` to git
- ✅ The `.env.example` file is safe to commit (it contains no real credentials)

## Troubleshooting

**"Error: .env file not found"**
- Run `./setup_env.sh` to create it
- Or manually copy `.env.example` to `.env` and fill in values

**"SSH_PASSWORD not found"**
- Make sure your `.env` file has `SSH_PASSWORD=...` (no spaces around `=`)
- Check that `.env` is in the project root directory

**"OPENAI_API_KEY not found"**
- Make sure your `.env` file has `OPENAI_API_KEY=...`
- Scripts will fall back to `openaikey` file if it exists (for backward compatibility)

