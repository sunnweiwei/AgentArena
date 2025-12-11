#!/bin/bash
# Setup script to create .env file from existing key files or template

set -e

ENV_FILE=".env"
EXAMPLE_FILE=".env.example"

echo "Setting up .env file..."

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "Warning: .env file already exists."
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. Keeping existing .env file."
        exit 0
    fi
fi

# Try to migrate from existing key files
if [ -f "key" ] && [ -f "openaikey" ]; then
    echo "Found existing key files. Migrating to .env..."
    {
        echo "# Server Configuration"
        echo "# Generated from existing key files"
        echo ""
        echo "SSH_PASSWORD=$(cat key | tr -d '\n')"
        echo "OPENAI_API_KEY=$(cat openaikey | tr -d '\n')"
        echo ""
        echo "# Server details (optional - defaults shown)"
        echo "SERVER_HOST=sf.lti.cs.cmu.edu"
        echo "SERVER_USER=weiweis"
        echo "REMOTE_PATH=/usr1/data/weiweis/chat_server"
    } > "$ENV_FILE"
    echo "✓ Created .env file from existing key files"
    echo ""
    echo "Note: You may want to delete the old 'key' and 'openaikey' files for security:"
    echo "  rm key openaikey"
elif [ -f "key" ]; then
    echo "Found 'key' file but not 'openaikey'."
    read -p "Enter your OpenAI API key: " -s openai_key
    echo
    {
        echo "# Server Configuration"
        echo ""
        echo "SSH_PASSWORD=$(cat key | tr -d '\n')"
        echo "OPENAI_API_KEY=$openai_key"
        echo ""
        echo "# Server details (optional - defaults shown)"
        echo "SERVER_HOST=sf.lti.cs.cmu.edu"
        echo "SERVER_USER=weiweis"
        echo "REMOTE_PATH=/usr1/data/weiweis/chat_server"
    } > "$ENV_FILE"
    echo "✓ Created .env file"
else
    # Create from template
    if [ ! -f "$EXAMPLE_FILE" ]; then
        echo "Creating .env.example template..."
        {
            echo "# Server Configuration"
            echo "# Copy this file to .env and fill in your actual values"
            echo "# DO NOT commit .env to git - it contains sensitive information"
            echo ""
            echo "# SSH password for server access"
            echo "SSH_PASSWORD=your_ssh_password_here"
            echo ""
            echo "# OpenAI API Key"
            echo "OPENAI_API_KEY=your_openai_api_key_here"
            echo ""
            echo "# Server details (optional - defaults shown)"
            echo "SERVER_HOST=sf.lti.cs.cmu.edu"
            echo "SERVER_USER=weiweis"
            echo "REMOTE_PATH=/usr1/data/weiweis/chat_server"
        } > "$EXAMPLE_FILE"
        echo "✓ Created .env.example template"
    fi
    
    echo "No existing key files found."
    echo "Please create .env file manually:"
    echo "  cp $EXAMPLE_FILE $ENV_FILE"
    echo "  # Then edit $ENV_FILE and fill in your credentials"
    exit 1
fi

echo ""
echo "✓ Setup complete! Your .env file is ready."
echo ""
echo "Important: Make sure .env is in .gitignore and never commit it to git!"

