/**
 * Frontend MCP Bridge
 * Connects to local MCP servers and handles tool calls
 */

class MCPBridge {
  constructor() {
    this.servers = new Map() // server_id -> { session, tools }
    this.localServerUrl = null
  }

  /**
   * Initialize MCP bridge by connecting to local MCP servers
   * The local server runs on a simple HTTP endpoint
   */
  async initialize(mcpConfigs) {
    // Try to connect to local MCP bridge server
    // This will be a simple HTTP server running on localhost
    this.localServerUrl = 'http://localhost:8766'
    
    for (const config of mcpConfigs) {
      try {
        await this.connectServer(config)
      } catch (error) {
        console.error(`[MCP Bridge] Failed to connect to ${config.server_id}:`, error)
      }
    }
  }

  async connectServer(config) {
    const { server_id, command, args, env } = config
    
    // Send request to local bridge server to connect to MCP server
    const response = await fetch(`${this.localServerUrl}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ server_id, command, args, env })
    })

    if (!response.ok) {
      throw new Error(`Failed to connect: ${response.statusText}`)
    }

    const data = await response.json()
    this.servers.set(server_id, {
      tools: data.tools || [],
      connected: true
    })

    console.log(`[MCP Bridge] Connected to ${server_id}, found ${data.tools.length} tools`)
    return true
  }

  async callTool(serverId, toolName, arguments_) {
    if (!this.servers.has(serverId)) {
      throw new Error(`Server ${serverId} not connected`)
    }

    // Call tool via local bridge server
    const response = await fetch(`${this.localServerUrl}/call_tool`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        server_id: serverId,
        tool_name: toolName,
        arguments: arguments_
      })
    })

    if (!response.ok) {
      throw new Error(`Tool call failed: ${response.statusText}`)
    }

    const result = await response.json()
    return result
  }

  getTools(serverId) {
    const server = this.servers.get(serverId)
    return server ? server.tools : []
  }

  getAllTools() {
    const allTools = []
    for (const [serverId, server] of this.servers) {
      allTools.push(...server.tools.map(tool => ({
        ...tool,
        server_id: serverId
      })))
    }
    return allTools
  }
}

// Export singleton instance
export const mcpBridge = new MCPBridge()

