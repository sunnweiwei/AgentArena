#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

puts "Deploying streaming support to agent service..."

# Kill service
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main"
expect "password:"
send "$password\r"
expect eof

# Copy updated files
spawn scp -o StrictHostKeyChecking=no ./agent_service/agent_main.py ./agent_service/agent/trae_wrapper.py $server:$service_dir/
expect "password:"
send "$password\r"
expect eof

spawn scp -o StrictHostKeyChecking=no ./agent_service/agent/trae_wrapper.py $server:$service_dir/agent/
expect "password:"
send "$password\r"
expect eof

# Clear cache
spawn ssh -o StrictHostKeyChecking=no $server "cd $service_dir && find . -type f -name '*.pyc' -delete && find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
expect "password:"
send "$password\r"
expect eof

# Restart
spawn ssh -o StrictHostKeyChecking=no $server "cd $service_dir; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"
expect "password:"
send "$password\r"
expect eof

puts "\nStreaming support deployed! Service restarting..."
puts "Wait a few seconds, then check: curl http://sf.lti.cs.cmu.edu:8001/health"
