#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

# Kill all agent processes
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main; pkill -9 -f start.sh"
expect "password:"
send "$password\r"
expect eof

# Delete log
spawn ssh -o StrictHostKeyChecking=no $server "rm -f $service_dir/service.log"
expect "password:"
send "$password\r"
expect eof

# Start fresh
spawn ssh -o StrictHostKeyChecking=no $server "cd $service_dir; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"
expect "password:"
send "$password\r"
expect eof

puts "\nFresh start"
