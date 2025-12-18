#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set remote_path "/usr1/data/weiweis/chat_server"

puts "Installing Node.js via nvm..."
spawn ssh -o StrictHostKeyChecking=no $server bash
expect "password:"
send "$password\r"
expect "$ "
send "export NVM_DIR=\"\$HOME/.nvm\"\r"
expect "$ "
send "\[ -s \"\$NVM_DIR/nvm.sh\" \] && \\. \"\$NVM_DIR/nvm.sh\"\r"
expect "$ "
send "nvm install --lts\r"
expect "$ "
send "nvm use --lts\r"
expect "$ "
send "nvm alias default node\r"
expect "$ "
send "exit\r"
expect eof

puts "\nSetting up frontend..."
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
send "npm install\r"
expect "$ "
send "exit\r"
expect eof

puts "\n✅ Setup complete!"







