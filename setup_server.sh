#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set remote_path "/usr1/data/weiweis/chat_server"

puts "Setting up backend (using virtualenv)..."
spawn ssh -o StrictHostKeyChecking=no $server "cd $remote_path/backend && python3 -m pip install --user virtualenv && python3 -m virtualenv venv && source venv/bin/activate && pip install -r requirements.txt"
expect "password:"
send "$password\r"
expect eof

puts "\nChecking for npm..."
spawn ssh -o StrictHostKeyChecking=no $server "which npm || (curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash && source ~/.bashrc && nvm install node && nvm use node)"
expect "password:"
send "$password\r"
expect eof

puts "\nSetting up frontend..."
spawn ssh -o StrictHostKeyChecking=no $server "cd $remote_path/frontend && source ~/.bashrc 2>/dev/null; export PATH=\$HOME/.nvm/versions/node/*/bin:\$PATH; npm install"
expect "password:"
send "$password\r"
expect eof

puts "\nSetup complete!"



