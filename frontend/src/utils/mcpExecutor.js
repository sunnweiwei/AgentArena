/**
 * MCP Executor - Runs MCP tools locally in the browser
 * Uses a lightweight Node.js server that auto-starts via npx
 */

class MCPExecutor {
  constructor() {
    this.serverProcess = null
    this.serverUrl = 'http://localhost:8767'
    this.isStarting = false
    this.connectedServers = new Map() // server_id -> { tools, config }
  }

  /**
   * Auto-start the MCP server using npx (no installation needed)
   */
  async ensureServerRunning() {
    if (this.isStarting) {
      // Wait for server to start
      await new Promise(resolve => {
        const checkInterval = setInterval(async () => {
          if (await this.checkServerHealth()) {
            clearInterval(checkInterval)
            resolve()
          }
        }, 500)
        setTimeout(() => {
          clearInterval(checkInterval)
          resolve()
        }, 10000) // Timeout after 10s
      })
      return
    }

    // Check if server is already running
    if (await this.checkServerHealth()) {
      return true
    }

    this.isStarting = true

    try {
      // Try to start server using npx (runs without installation)
      // This will spawn a Node.js process that runs the MCP bridge
      const response = await fetch('/api/mcp/start-server', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      if (response.ok) {
        // Server starting, wait a bit
        await new Promise(resolve => setTimeout(resolve, 2000))
        
        // Poll until server is ready
        for (let i = 0; i < 10; i++) {
          if (await this.checkServerHealth()) {
            this.isStarting = false
            return true
          }
          await new Promise(resolve => setTimeout(resolve, 500))
        }
      }
    } catch (error) {
      console.error('[MCP Executor] Failed to start server:', error)
    }

    this.isStarting = false
    return false
  }

  async checkServerHealth() {
    try {
      const response = await fetch(`${this.serverUrl}/health`, {
        method: 'GET',
        mode: 'cors',
        cache: 'no-cache',
        signal: AbortSignal.timeout(1000)
      })
      return response && response.ok
    } catch {
      return false
    }
  }

  /**
   * Connect to an MCP server (configured in frontend)
   */
  async connectServer(config) {
    await this.ensureServerRunning()

    const { server_id, command, args, env } = config

    try {
      const response = await fetch(`${this.serverUrl}/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_id, command, args, env }),
        mode: 'cors'
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.error || `Failed to connect: ${response.statusText}`)
      }

      const data = await response.json()
      if (data.error) {
        throw new Error(data.error)
      }

      this.connectedServers.set(server_id, {
        tools: data.tools || [],
        config
      })

      console.log(`[MCP Executor] Connected to ${server_id}, found ${data.tools.length} tools`)
      return true
    } catch (error) {
      console.error(`[MCP Executor] Connection error for ${server_id}:`, error)
      throw error
    }
  }

  /**
   * Execute an MCP tool call
   */
  async callTool(serverId, toolName, arguments_) {
    if (!this.connectedServers.has(serverId)) {
      throw new Error(`Server ${serverId} not connected`)
    }

    try {
      const response = await fetch(`${this.serverUrl}/call_tool`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server_id: serverId,
          tool_name: toolName,
          arguments: arguments_
        }),
        mode: 'cors'
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(error.error || `Tool call failed: ${response.statusText}`)
      }

      const result = await response.json()
      if (result.error) {
        throw new Error(result.error)
      }

      return result
    } catch (error) {
      console.error(`[MCP Executor] Tool call error:`, error)
      throw error
    }
  }

  getTools(serverId) {
    const server = this.connectedServers.get(serverId)
    return server ? server.tools : []
  }

  getAllTools() {
    const allTools = []
    for (const [serverId, server] of this.connectedServers) {
      allTools.push(...server.tools.map(tool => ({
        ...tool,
        server_id: serverId
      })))
    }
    return allTools
  }
}

export const mcpExecutor = new MCPExecutor()

