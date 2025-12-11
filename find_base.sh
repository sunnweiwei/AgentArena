#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"

# Find all base.py files
spawn ssh -o StrictHostKeyChecking=no $server "find $service_dir -name 'base.py' -o -name 'base.pyc'"
expect "password:"
send "$password\r"
expect eof
