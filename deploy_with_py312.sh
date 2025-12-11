#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

# Kill old service
spawn ssh -o StrictHostKeyChecking=no $server "pkill -9 -f agent_main"
expect "password:"
send "$password\r"
expect eof

# Copy all files
spawn scp -o StrictHostKeyChecking=no -r ./agent_service/agent ./agent_service/utils ./agent_service/trae_agent ./agent_service/agent_main.py ./agent_service/config.py ./agent_service/requirements.txt $server:$service_dir/
expect "password:"
send "$password\r"
expect eof

# Install dependencies in Python 3.12 environment and start
set cmd "source $conda_sh; conda activate agent_py312; cd $service_dir; pip install -r requirements.txt; setsid nohup python agent_main.py > service.log 2>&1 < /dev/null & echo \$!"

spawn ssh -o StrictHostKeyChecking=no $server "bash -c '$cmd'"
expect "password:"
send "$password\r"
expect eof

puts "\nAgent service deployed with Python 3.12 and trae-agent tools"
