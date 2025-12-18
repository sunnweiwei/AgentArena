# Chat System Overview

This document captures the key requirements, architecture, and operational procedures for the user-agent chat data collection system so that any engineer can continue work without reverse-engineering the codebase.

---

## 1. Business Requirements

### User Experience
* ChatGPT-style UI with Chat history sidebar and responsive layout (mobile + desktop).
* Username-based login (any string). Login input is always part of the main chat UI.
* Sidebar shows all chats with latest user activity first, animation when a chat jumps to the top, “New Chat” reuses empty current chat.
* Close/open sidebar button (desktop + mobile), theme toggle (light/dark), logout area showing user avatar & info.
* Input bar is always at the bottom. If WebSocket is disconnected, the input is disabled and a notice tells the user (“Disconnected. Reconnecting…”).
* Auto-scroll to latest messages, send button styled like ChatGPT.

### Functional Goals
* Handle 100-500 concurrent users.
* Real-time chatting through WebSockets.
* Chats are tied to users; selecting an old chat must keep messages isolated.
* Prevent “phantom” chats (no empty chats in sidebar).
* Deployment target: `weiweis@sf.lti.cs.cmu.edu` under `/usr1/data/weiweis/chat_server`.

---

## 2. Architecture

### Backend (FastAPI)
* Path: `/usr1/data/weiweis/chat_server/backend`
* Framework: FastAPI + SQLAlchemy + SQLite.
* Key file: `backend/main.py`
* WebSocket endpoint: `/ws/chat/{chat_id}/{user_id}`
  * Each message opens its own `SessionLocal()` to avoid holding DB connections.
  * Connection pool tuned for concurrency (`pool_size=20`, `max_overflow=40`, `pool_pre_ping=True`).
* API endpoints:
  * `POST /api/auth/login`
  * `GET /api/chats`, `POST /api/chats`
  * `GET /api/chats/{chat_id}`
  * `PUT /api/chats/{chat_id}/title`
  * `POST /api/chats/{chat_id}/messages`
  * `GET /health`

### Frontend (React + Vite)
* Path: `/usr1/data/weiweis/chat_server/frontend`
* Key components:
  * `ChatInterface.jsx` – orchestrates login state, sidebar, chat selection.
  * `ChatWindow.jsx` – handles WebSocket connections, message list, connection notices.
  * `Sidebar.jsx` – chat list, theme toggle, logout, new chat button.
  * `MessageInput.jsx`, `MessageList.jsx`, CSS files.
* WebSocket proxy configured in `vite.config.js` (proxy `/ws` → backend).

### Deployment Scripts
* `start_services.sh` – starts backend + frontend with health checks.
* `monitor_services.sh` – restart services if health checks fail (run via cron: `*/5 * * * * /usr1/data/weiweis/chat_server/monitor_services.sh`).
* `keep_alive.sh` – optional looped backend runner.
* `run_services.sh` – convenience script (older; `start_services.sh` supersedes it).
* Docs: `SERVER_SETUP.md` (server commands), `README.md` (project setup).

---

## 3. Running the System

### On Server (recommended)
```bash
ssh weiweis@sf.lti.cs.cmu.edu
cd /usr1/data/weiweis/chat_server
./start_services.sh
```
*Backend listens on 8000, frontend on 3000.*

### Manual Commands
**Backend**
```bash
cd backend
source venv/bin/activate
nohup python main.py > ../logs/backend.log 2>&1 &
```

**Frontend**
```bash
cd frontend
source ~/.nvm/nvm.sh
nohup npm run dev -- --host 0.0.0.0 > ../logs/frontend.log 2>&1 &
```

### Monitoring
* Health: `curl -s http://localhost:8000/health`
* Processes: `ps aux | grep -E 'python.*main.py|node.*vite'`
* Frontend status: `ss -tuln | grep :3000`

### Logs
* Backend: `/usr1/data/weiweis/chat_server/logs/backend.log`
* Frontend: `/usr1/data/weiweis/chat_server/logs/frontend.log`
* Monitor: `/usr1/data/weiweis/chat_server/logs/monitor.log`

---

## 4. Known Design Decisions
* **No queued messages** when disconnected. Input is disabled and a banner informs the user until socket reconnects.
* **Chat ordering** is based on last user message timestamp, not server `updated_at`.
* **Empty chats** are suppressed from sidebar; `createNewChat` reuses current chat if it has no messages.
* **WebSocket isolation**: every WS event checks `activeChatRef` on the frontend and chat ownership on the backend.
* **DB reliability**: short-lived sessions prevent pool exhaustion.

---

## 5. Future Work / Tips
* Replace simulated agent response inside `websocket_endpoint` with a real LLM call.
* Implement pagination for message history if chat size grows.
* Consider moving to Postgres for higher concurrency and to avoid SQLite locking limits.
* Add automated tests for chat ordering and reconnection flows.
* Harden deployment (systemd service, HTTPS reverse proxy) if this goes to production.

---

This document, `README.md`, and `SERVER_SETUP.md` together provide the operational and design context necessary for continued development.







