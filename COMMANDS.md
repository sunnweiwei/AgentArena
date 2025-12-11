# Common Server Commands

Quick reference for syncing code, restarting services, and checking server status.

## Prerequisites

**Setup:** Create a `.env` file in the project root with your credentials:
```bash
cp .env.example .env
# Then edit .env and fill in your SSH_PASSWORD and OPENAI_API_KEY
```

The password is loaded from the `.env` file. All commands use `expect` to handle password authentication automatically.

**Note:** If you have existing `key` and `openaikey` files, you can migrate them to `.env`:
```bash
echo "SSH_PASSWORD=$(cat key)" > .env
echo "OPENAI_API_KEY=$(cat openaikey)" >> .env
```

---

## Sync Code to Server

### Backend Files

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no backend/main.py weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/backend/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Frontend Files

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no frontend/src/components/ChatWindow.jsx weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/frontend/src/components/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Frontend CSS Files

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no frontend/src/components/ChatWindow.css weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/frontend/src/components/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Frontend Global CSS

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no frontend/src/index.css weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/frontend/src/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Frontend HTML

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn scp -o StrictHostKeyChecking=no frontend/index.html weiweis@sf.lti.cs.cmu.edu:/usr1/data/weiweis/chat_server/frontend/
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

---

## Restart Services

### Restart Both Backend and Frontend

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "cd /usr1/data/weiweis/chat_server && ./start_services.sh"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Kill Stale Processes and Restart

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "cd /usr1/data/weiweis/chat_server && pkill -f 'python.*main.py' || true && sleep 2 && ./start_services.sh"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

---

## Check Server Status

### Check Backend Logs

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "tail -50 /usr1/data/weiweis/chat_server/logs/backend.log"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Check Frontend Logs

```bash
cd /Users/sunweiwei/NLP/base_project
source load_env.sh
export PASSWORD=$SSH_PASSWORD
expect <<'EOF'
spawn ssh -o StrictHostKeyChecking=no weiweis@sf.lti.cs.cmu.edu "tail -50 /usr1/data/weiweis/chat_server/logs/frontend.log"
expect "password:"
send "$env(PASSWORD)\r"
expect eof
EOF
```

### Check Service Health

```bash
# Backend health check
curl -s http://sf.lti.cs.cmu.edu:8000/health

# Frontend (check if page loads)
curl -s -o /dev/null -w "%{http_code}" http://sf.lti.cs.cmu.edu:3000/
```

---

## Quick Reference

**Server Details:**
- Host: `sf.lti.cs.cmu.edu`
- User: `weiweis`
- Backend Path: `/usr1/data/weiweis/chat_server/backend/`
- Frontend Path: `/usr1/data/weiweis/chat_server/frontend/`
- Logs Path: `/usr1/data/weiweis/chat_server/logs/`
- Backend Port: `8000`
- Frontend Port: `3000`

**Common File Paths:**
- Backend: `backend/main.py`
- Frontend Components: `frontend/src/components/`
- Frontend Global: `frontend/src/index.css`, `frontend/index.html`
- Frontend Styles: `frontend/src/components/*.css`

---

## Notes

- Always sync files **before** restarting services
- Frontend changes (CSS/JSX) usually don't require restart - Vite hot-reloads
- Backend changes **always** require restart
- If services fail to start, check logs first
- The `start_services.sh` script handles both backend and frontend startup



