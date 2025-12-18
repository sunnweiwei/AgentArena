# Server Setup Complete! 🎉

The chat system has been successfully deployed to your server at:
- **Server**: `sf.lti.cs.cmu.edu`
- **Path**: `/usr1/data/weiweis/chat_server`

## What's Installed

✅ **Backend** (FastAPI)
- Python virtual environment created
- All dependencies installed (FastAPI, SQLite, WebSocket support)
- Ready to run on port 8000

✅ **Frontend** (React + Vite)
- Node.js v24.11.1 installed via nvm
- All npm packages installed
- Ready to run on port 3000

## How to Run the Services

### Option 1: Run Both Services (Recommended)

Use the provided script:
```bash
./run_services.sh
```

### Option 2: Run Manually

**Start Backend:**
```bash
ssh weiweis@sf.lti.cs.cmu.edu
cd /usr1/data/weiweis/chat_server/backend
source venv/bin/activate
python main.py
```

**Start Frontend (in another terminal):**
```bash
ssh weiweis@sf.lti.cs.cmu.edu
cd /usr1/data/weiweis/chat_server/frontend
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
npm run dev -- --host
```

## Accessing the Application

Once both services are running:
- **Frontend**: `http://sf.lti.cs.cmu.edu:3000` (or use the server's public IP/domain)
- **Backend API**: `http://sf.lti.cs.cmu.edu:8000`

## Important Notes

1. **Ports**: Make sure ports 3000 and 8000 are open on the server firewall
2. **Frontend URL**: The frontend is configured to connect to `localhost:8000` for the backend. If you need to access from outside, you may need to update the frontend API URLs in the components
3. **Running in Background**: To run services in the background, use `nohup` or `screen`/`tmux`:
   ```bash
   nohup python main.py > backend.log 2>&1 &
   nohup npm run dev -- --host > frontend.log 2>&1 &
   ```

## Checking Running Services

```bash
ssh weiweis@sf.lti.cs.cmu.edu 'ps aux | grep -E "python main.py|vite"'
```

## Stopping Services

```bash
ssh weiweis@sf.lti.cs.cmu.edu 'pkill -f "python main.py" && pkill -f vite'
```

## Database

The SQLite database will be created automatically at:
`/usr1/data/weiweis/chat_server/backend/chat_data.db`

## Troubleshooting

- If backend doesn't start: Check Python virtual environment is activated
- If frontend doesn't start: Make sure nvm is loaded (`source ~/.nvm/nvm.sh`)
- If ports are in use: Change ports in `main.py` (backend) and `vite.config.js` (frontend)







