#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

# Clear all Python cache
spawn ssh -o StrictHostKeyChecking=no $server "find $service_dir -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true"
expect "password:"
send "$password\r"
expect eof

# Restart
set cmd "source $conda_sh; conda activate agent_py312; cd $service_dir; pkill -9 -f agent_main; setsid nohup python agent_main.py > service.log 2>&1 < /dev/null & echo \$!"

spawn ssh -o StrictHostKeyChecking=no $server "bash -c '$cmd'"
expect "password:"
send "$password\r"
expect eof

puts "\nCache cleared and restarted"
