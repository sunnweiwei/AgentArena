#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set chat_backend_dir "/usr1/data/weiweis/chat_server/backend"

# Restart chat server backend
spawn ssh -o StrictHostKeyChecking=no $server "cd $chat_backend_dir && source venv/bin/activate && nohup python main.py > ../logs/backend.log 2>&1 &"
expect "password:"
send "$password\r"
expect eof

puts "\nChat server restarted"
