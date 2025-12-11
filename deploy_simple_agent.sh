#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

# Copy updated files (NOT trae_agent)
spawn scp -o StrictHostKeyChecking=no agent_service/agent_main.py agent_service/requirements.txt $server:$service_dir/
expect "password:"
send "$password\r"
expect eof

# Restart with simple agent
set cmd "source $conda_sh; conda activate agent_service_env; cd $service_dir; pkill -9 -f agent_main; setsid nohup python agent_main.py > service.log 2>&1 < /dev/null & echo \$!"

spawn ssh -o StrictHostKeyChecking=no $server "bash -c '$cmd'"
expect "password:"
send "$password\r"
expect eof

puts "\nAgent service restarted with simple custom agent (no trae-agent)"
