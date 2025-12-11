#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

# Copy startup script
spawn scp -o StrictHostKeyChecking=no ./agent_service/start.sh $server:$service_dir/
expect "password:"
send "$password\r"
expect eof

# Make it executable and run
spawn ssh -o StrictHostKeyChecking=no $server "chmod +x $service_dir/start.sh; pkill -9 -f agent_main; cd $service_dir; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"
expect "password:"
send "$password\r"
expect eof

puts "\nService started with startup script"
