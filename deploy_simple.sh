#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set remote_path "/usr1/data/weiweis/chat_server"

# Create remote directory
spawn ssh -o StrictHostKeyChecking=no $server "mkdir -p $remote_path"
expect "password:"
send "$password\r"
expect eof

# Copy backend
spawn scp -o StrictHostKeyChecking=no -r backend $server:$remote_path/
expect "password:"
send "$password\r"
expect eof

# Copy frontend
spawn scp -o StrictHostKeyChecking=no -r frontend $server:$remote_path/
expect "password:"
send "$password\r"
expect eof

# Copy README
spawn scp -o StrictHostKeyChecking=no README.md $server:$remote_path/ 2>/dev/null
expect {
    "password:" {
        send "$password\r"
        expect eof
    }
    eof
}

puts "\nFiles copied. Setting up backend..."
spawn ssh -o StrictHostKeyChecking=no $server "cd $remote_path/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
expect "password:"
send "$password\r"
expect eof

puts "\nSetting up frontend..."
spawn ssh -o StrictHostKeyChecking=no $server "cd $remote_path/frontend && npm install"
expect "password:"
send "$password\r"
expect eof

puts "\nDeployment complete!"
puts "To run backend: ssh $server 'cd $remote_path/backend && source venv/bin/activate && python main.py'"
puts "To run frontend: ssh $server 'cd $remote_path/frontend && npm run dev'"



