#!/bin/bash
# Helper script to load .env file
# Usage: source load_env.sh

if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
elif [ -f key ] && [ -f openaikey ]; then
    # Fallback: load from old key files for backward compatibility
    export SSH_PASSWORD=$(cat key 2>/dev/null)
    export OPENAI_API_KEY=$(cat openaikey 2>/dev/null)
    echo "Warning: Using legacy key files. Please migrate to .env file." >&2
else
    echo "Error: .env file not found. Please create .env from .env.example" >&2
    exit 1
fi

