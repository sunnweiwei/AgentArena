#!/usr/bin/expect -f

# Load password from .env (falls back to key file for backward compatibility)
set password [exec bash load_env_for_expect.sh]
set server "weiweis@sf.lti.cs.cmu.edu"
set remote_path "/usr1/data/weiweis/chat_server"

puts "Starting backend server..."
spawn ssh -o StrictHostKeyChecking=no $server bash
expect "password:"
send "$password\r"
expect "$ "
send "cd $remote_path/backend\r"
expect "$ "
send "source venv/bin/activate\r"
expect "$ "
send "python main.py &\r"
expect "$ "
send "echo 'Backend started on port 8000'\r"
expect "$ "
send "exit\r"
expect eof

puts "\nStarting frontend server..."
spawn ssh -o StrictHostKeyChecking=no $server bash
expect "password:"
send "$password\r"
expect "$ "
send "cd $remote_path/frontend\r"
expect "$ "
send "export NVM_DIR=\"\$HOME/.nvm\"\r"
expect "$ "
send "\[ -s \"\$NVM_DIR/nvm.sh\" \] && \\. \"\$NVM_DIR/nvm.sh\"\r"
expect "$ "
send "npm run dev -- --host &\r"
expect "$ "
send "echo 'Frontend started'\r"
expect "$ "
send "exit\r"
expect eof

puts "\n✅ Services started!"
puts "\nTo check running services:"
puts "  ssh $server 'ps aux | grep -E \"python main.py|vite\"'"
puts "\nTo stop services:"
puts "  ssh $server 'pkill -f \"python main.py\" && pkill -f vite'"



