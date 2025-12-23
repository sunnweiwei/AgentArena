#!/bin/bash

# MCP Filesystem Server Installation Script
# This script installs and tests the MCP filesystem server

set -e

echo "=== Installing MCP Filesystem Server ==="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"
echo ""

# Install the MCP filesystem server globally
echo "Installing @modelcontextprotocol/server-filesystem..."
npm install -g @modelcontextprotocol/server-filesystem

echo ""
echo "=== Installation Complete ==="
echo ""

# Verify installation
echo "Verifying installation..."
if npx @modelcontextprotocol/server-filesystem --help &> /dev/null; then
    echo "✓ MCP Filesystem Server installed successfully!"
else
    echo "✗ Installation verification failed"
    exit 1
fi

echo ""
echo "=== Setup Summary ==="
echo "Server installed: @modelcontextprotocol/server-filesystem"
echo "Workspace directory: /Users/sunweiwei/NLP/base_project"
echo "Config file: mcp_config.json"
echo ""
echo "Next steps:"
echo "1. Review mcp_config.json"
echo "2. Integrate with your agent system"
echo "3. See MCP_FILESYSTEM_SETUP.md for detailed usage"
echo ""
