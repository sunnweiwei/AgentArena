#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

# Copy fixed wrapper
spawn scp -o StrictHostKeyChecking=no ./agent_service/agent/trae_wrapper.py $server:$service_dir/agent/
expect "password:"
send "$password\r"
expect eof

# Restart
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main; cd $service_dir; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"
expect "password:"
send "$password\r"
expect eof

puts "\nFixed and restarted"
