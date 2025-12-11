#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"

spawn ssh -o StrictHostKeyChecking=no $server "python3 -c 'import sys; print(sys.version)'; head -20 /usr1/data/weiweis/agent_service/trae_agent/tools/base.py"
expect "password:"
send "$password\r"
expect eof
