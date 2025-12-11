# Development & Deployment Workflow

This project runs on the CMU server (`sf.lti.cs.cmu.edu`) without git. To make sure your changes actually reach the running system, follow the workflow below.

## Prerequisites

**Environment Setup:** Before deploying, make sure you have a `.env` file with your credentials:
```bash
./setup_env.sh  # Auto-migrates from key/openaikey files if they exist
# Or manually: cp .env.example .env and fill in values
```

See `ENV_SETUP.md` for detailed instructions.

---

## 1. Edit Locally

1. Make code changes in your local workspace (e.g. update `backend/main.py` or files under `frontend/src`).
2. Test locally if possible (`npm run dev`, `python backend/main.py`).

## 2. Deploy to Server

Copy only the files you changed. Examples:

```bash
# Load environment variables
source load_env.sh

# Backend file
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no backend/main.py weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/backend/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF

# Frontend component
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no frontend/src/components/ChatWindow.jsx weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/frontend/src/components/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

Or use the Python deploy script:
```bash
python deploy.py
```

See `COMMANDS.md` for more examples.

## 3. Restart Services

Use the commands from `COMMANDS.md`:

```bash
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "cd /usr1/data/weiweis/chat_server && ./start_services.sh"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

## 4. Verify

* Backend health: `curl -s http://sf.lti.cs.cmu.edu:8000/health`
* Frontend running: visit `http://sf.lti.cs.cmu.edu:3000/`
* Check logs if needed (`/usr1/data/weiweis/chat_server/logs/…`)

## 5. Document Changes

Update `SYSTEM_OVERVIEW.md`, `README.md`, or other docs if you add features or change the workflow.

---

Following this loop ensures every requirement change (like new UI behavior or backend logic) is actually deployed and visible to users.***



