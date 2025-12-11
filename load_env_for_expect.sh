#!/bin/bash
# Helper for expect scripts to load password from .env
# Usage in expect: set password [exec bash load_env_for_expect.sh]

if [ -f .env ]; then
    # Load .env and extract SSH_PASSWORD
    export $(grep -v '^#' .env | grep SSH_PASSWORD | xargs)
    echo "$SSH_PASSWORD"
elif [ -f key ]; then
    # Fallback to key file
    cat key
else
    echo "Error: .env file not found and 'key' file doesn't exist" >&2
    exit 1
fi

