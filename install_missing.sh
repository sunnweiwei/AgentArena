#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

# Copy requirements
spawn scp -o StrictHostKeyChecking=no ./agent_service/requirements.txt $server:$service_dir/
expect "password:"
send "$password\r"
expect eof

# Install and restart
set cmd "source $conda_sh; conda activate agent_py312; cd $service_dir; pip install -r requirements.txt; pkill -9 -f agent_main; setsid nohup ./start.sh > service.log 2>&1 < /dev/null &"

spawn ssh -o StrictHostKeyChecking=no $server "bash -c '$cmd'"
expect "password:"
send "$password\r"
expect eof

puts "\nDependencies installed and restarted"
