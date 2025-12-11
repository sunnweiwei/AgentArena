#!/bin/bash

# Activate conda
source /usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh
conda activate agent_py312

# Change to service directory
cd /usr1/data/weiweis/agent_service

# Run the service
python agent_main.py
