#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set remote_path "/usr1/data/weiweis/chat_server"

puts "Installing pip for Python3..."
spawn ssh -o StrictHostKeyChecking=no $server "python3 -m ensurepip --user || curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python3 /tmp/get-pip.py --user"
expect "password:"
send "$password\r"
expect eof

puts "\nSetting up backend..."
spawn ssh -o StrictHostKeyChecking=no $server "cd $remote_path/backend && export PATH=\$HOME/.local/bin:\$PATH && python3 -m pip install --user virtualenv && python3 -m virtualenv venv && source venv/bin/activate && pip install -r requirements.txt"
expect "password:"
send "$password\r"
expect eof

puts "\nInstalling Node.js via nvm..."
spawn ssh -o StrictHostKeyChecking=no $server bash -c "export NVM_DIR=\"\$HOME/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\" && nvm install --lts && nvm use --lts && nvm alias default node"
expect "password:"
send "$password\r"
expect eof

puts "\nSetting up frontend..."
spawn ssh -o StrictHostKeyChecking=no $server bash -c "cd $remote_path/frontend && export NVM_DIR=\"\$HOME/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\" && npm install"
expect "password:"
send "$password\r"
expect eof

puts "\n✅ Setup complete!"
puts "\nTo run backend:"
puts "  ssh $server 'cd $remote_path/backend && source venv/bin/activate && python main.py'"
puts "\nTo run frontend:"
puts "  ssh $server 'cd $remote_path/frontend && export NVM_DIR=\"\$HOME/.nvm\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && \. \"\$NVM_DIR/nvm.sh\" && npm run dev'"







