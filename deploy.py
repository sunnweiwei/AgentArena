#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read password from .env, fallback to key file for backward compatibility
password = os.getenv('SSH_PASSWORD')
if not password:
    key_file = Path('key')
    if key_file.exists():
        password = key_file.read_text().strip()
        print("Warning: Using legacy 'key' file. Please migrate to .env file.", file=sys.stderr)
    else:
        print("Error: SSH_PASSWORD not found in .env and 'key' file doesn't exist.", file=sys.stderr)
        sys.exit(1)

SERVER = os.getenv('SERVER_HOST', 'sf.lti.cs.cmu.edu')
SERVER_USER = os.getenv('SERVER_USER', 'weiweis')
SERVER = f"{SERVER_USER}@{SERVER}"
REMOTE_PATH = os.getenv('REMOTE_PATH', '/usr1/data/weiweis/chat_server')

def run_ssh_command(cmd):
    """Run command on remote server using SSH"""
    ssh_cmd = f'ssh -o StrictHostKeyChecking=no {SERVER} "{cmd}"'
    proc = subprocess.Popen(
        ['expect', '-c', f'''
spawn {ssh_cmd}
expect "password:"
send "{password}\\r"
expect eof
'''],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()

def copy_files():
    """Copy files using scp"""
    # Create remote directory
    print("Creating remote directory...")
    run_ssh_command(f"mkdir -p {REMOTE_PATH}")
    
    # Copy backend
    print("Copying backend...")
    subprocess.run([
        'expect', '-c', f'''
spawn scp -o StrictHostKeyChecking=no -r backend {SERVER}:{REMOTE_PATH}/
expect "password:"
send "{password}\\r"
expect eof
'''
    ])
    
    # Copy frontend
    print("Copying frontend...")
    subprocess.run([
        'expect', '-c', f'''
spawn scp -o StrictHostKeyChecking=no -r frontend {SERVER}:{REMOTE_PATH}/
expect "password:"
send "{password}\\r"
expect eof
'''
    ])
    
    # Copy other files
    print("Copying other files...")
    for file in ['README.md', '.gitignore']:
        if os.path.exists(file):
            subprocess.run([
                'expect', '-c', f'''
spawn scp -o StrictHostKeyChecking=no {file} {SERVER}:{REMOTE_PATH}/
expect "password:"
send "{password}\\r"
expect eof
'''
            ])

def setup_backend():
    """Setup backend on server"""
    print("Setting up backend...")
    cmd = f"cd {REMOTE_PATH}/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    code, out, err = run_ssh_command(cmd)
    if code != 0:
        print(f"Backend setup error: {err}")
    else:
        print("Backend setup complete!")

def setup_frontend():
    """Setup frontend on server"""
    print("Setting up frontend...")
    cmd = f"cd {REMOTE_PATH}/frontend && npm install"
    code, out, err = run_ssh_command(cmd)
    if code != 0:
        print(f"Frontend setup error: {err}")
    else:
        print("Frontend setup complete!")

if __name__ == "__main__":
    print("Starting deployment...")
    copy_files()
    setup_backend()
    setup_frontend()
    print("\nDeployment complete!")
    print(f"\nTo run backend: ssh {SERVER} 'cd {REMOTE_PATH}/backend && source venv/bin/activate && python main.py'")
    print(f"To run frontend: ssh {SERVER} 'cd {REMOTE_PATH}/frontend && npm run dev'")



