#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

# Delete old file first
spawn ssh -o StrictHostKeyChecking=no $server "rm -f $service_dir/trae_agent/tools/base.py"
expect "password:"
send "$password\r"
expect eof

# Copy new file
spawn scp -o StrictHostKeyChecking=no ./agent_service/trae_agent/tools/base.py $server:$service_dir/trae_agent/tools/base.py
expect "password:"
send "$password\r"
expect eof

# Verify it's there
spawn ssh -o StrictHostKeyChecking=no $server "head -20 $service_dir/trae_agent/tools/base.py"
expect "password:"
send "$password\r"
expect eof

# Restart
set cmd "source $conda_sh; conda activate agent_py312; cd $service_dir; pkill -9 -f agent_main; setsid nohup python agent_main.py > service.log 2>&1 < /dev/null & echo \$!"

spawn ssh -o StrictHostKeyChecking=no $server "bash -c '$cmd'"
expect "password:"
send "$password\r"
expect eof

puts "\nForce updated and restarted"
