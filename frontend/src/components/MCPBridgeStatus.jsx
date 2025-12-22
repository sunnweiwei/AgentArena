import React, { useState, useEffect } from 'react'
import { mcpBridge } from '../utils/mcpBridge'
import './MCPBridgeStatus.css'

/**
 * Component to show MCP bridge status and auto-start local server
 */
export default function MCPBridgeStatus({ mcpServers, onToolsUpdate }) {
  const [status, setStatus] = useState('checking') // checking, connected, disconnected, starting
  const [error, setError] = useState(null)
  const [tools, setTools] = useState([])

  useEffect(() => {
    checkBridgeStatus()
  }, [mcpServers])

  const checkBridgeStatus = async () => {
    try {
      // Try to ping the local server
      const response = await fetch('http://localhost:8766/health', {
        method: 'GET',
        mode: 'cors',
        cache: 'no-cache'
      }).catch(() => null)

      if (response && response.ok) {
        setStatus('connected')
        setError(null)
        // Load tools from connected servers
        await loadTools()
      } else {
        setStatus('disconnected')
        setError('Local MCP server not running')
      }
    } catch (err) {
      setStatus('disconnected')
      setError('Cannot connect to local MCP server')
    }
  }

  const loadTools = async () => {
    if (!mcpServers || mcpServers.length === 0) return

    try {
      await mcpBridge.initialize(mcpServers.filter(s => s.bridge_url === 'local'))
      const allTools = mcpBridge.getAllTools()
      setTools(allTools)
      if (onToolsUpdate) {
        onToolsUpdate(allTools)
      }
    } catch (err) {
      console.error('[MCP Bridge] Failed to load tools:', err)
    }
  }

  const startLocalServer = async () => {
    setStatus('starting')
    setError(null)

    // Show instructions to start the server
    const instructions = `
To enable local MCP servers, please start the local MCP bridge server:

1. Open a terminal
2. Navigate to: ${window.location.origin.includes('localhost') ? 'your project directory' : 'the frontend_mcp_server directory'}
3. Run: python3 server.py

Or install as a service to auto-start.

The server will run on http://localhost:8766
    `.trim()

    alert(instructions)
    setStatus('disconnected')
    
    // Check again after a delay
    setTimeout(checkBridgeStatus, 2000)
  }

  if (status === 'checking') {
    return (
      <div className="mcp-bridge-status checking">
        <span>Checking MCP bridge...</span>
      </div>
    )
  }

  if (status === 'connected') {
    return (
      <div className="mcp-bridge-status connected">
        <span>✓ Local MCP bridge connected ({tools.length} tools available)</span>
      </div>
    )
  }

  return (
    <div className="mcp-bridge-status disconnected">
      <span>⚠ Local MCP bridge not running</span>
      <button onClick={startLocalServer} className="start-bridge-btn">
        Start Bridge Server
      </button>
      {error && <div className="error">{error}</div>}
    </div>
  )
}

