#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

# Delete old file
spawn ssh -o StrictHostKeyChecking=no $server "rm -f $service_dir/agent/trae_wrapper.py"
expect "password:"
send "$password\r"
expect eof

# Copy new file
spawn scp -o StrictHostKeyChecking=no ./agent_service/agent/trae_wrapper.py $server:$service_dir/agent/trae_wrapper.py
expect "password:"
send "$password\r"
expect eof

# Verify
spawn ssh -o StrictHostKeyChecking=no $server "head -15 $service_dir/agent/trae_wrapper.py"
expect "password:"
send "$password\r"
expect eof

# Restart
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main; cd $service_dir; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"
expect "password:"
send "$password\r"
expect eof

puts "\nForce updated wrapper"
