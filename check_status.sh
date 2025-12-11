#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"

spawn ssh -o StrictHostKeyChecking=no $server "tail -30 /usr1/data/weiweis/agent_service/service.log"
expect "password:"
send "$password\r"
expect eof
