#!/usr/bin/expect -f

set password [exec cat key]
set server "weiweis@sf.lti.cs.cmu.edu"
set service_dir "/usr1/data/weiweis/agent_service"
set conda_sh "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

puts "Creating Python 3.12 environment for agent service..."

# Create new environment with Python 3.12
set cmd "source $conda_sh; conda create -n agent_py312 python=3.12 -y"

spawn ssh -o StrictHostKeyChecking=no $server "$cmd"
expect "password:"
send "$password\r"
expect {
    "Proceed" { send "y\r"; exp_continue }
    timeout { puts "\nTimeout"; exit 1 }
    eof
}

puts "\nPython 3.12 environment created"
