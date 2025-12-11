#!/bin/bash

SERVER="weiweis@sf.lti.cs.cmu.edu"
REMOTE_PATH="/usr1/data/weiweis/chat_server"
# Load password from .env (falls back to key file for backward compatibility)
if [ -f .env ]; then
    source load_env.sh
    PASSWORD=$SSH_PASSWORD
elif [ -f key ]; then
    PASSWORD=$(cat key)
else
    echo "Error: .env file not found and 'key' file doesn't exist"
    exit 1
fi

# Function to run command on remote server
run_remote() {
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no "$SERVER" "$1"
}

# Function to copy files to remote server
copy_to_remote() {
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no -r "$1" "$SERVER:$2"
}

echo "Creating remote directory..."
run_remote "mkdir -p $REMOTE_PATH"

echo "Copying project files..."
# Copy backend
copy_to_remote "backend" "$REMOTE_PATH/"
# Copy frontend
copy_to_remote "frontend" "$REMOTE_PATH/"
# Copy other files
copy_to_remote "README.md" "$REMOTE_PATH/"
copy_to_remote ".gitignore" "$REMOTE_PATH/"

echo "Setting up backend on server..."
run_remote "cd $REMOTE_PATH/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"

echo "Setting up frontend on server..."
run_remote "cd $REMOTE_PATH/frontend && npm install"

echo "Setup complete!"
echo "To run the backend: cd $REMOTE_PATH/backend && source venv/bin/activate && python main.py"
echo "To run the frontend: cd $REMOTE_PATH/frontend && npm run dev"



