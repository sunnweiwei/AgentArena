#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"

# Kill ALL agent service processes to ensure no interference
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main; pkill -9 -f agent_service"
expect "password:"
send "$password\r"
expect eof

puts "\nAgent service completely stopped"
