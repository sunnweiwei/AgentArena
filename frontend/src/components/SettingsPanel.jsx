import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './SettingsPanel.css'

// Define available tools (frontend-only, backend doesn't need to know)
const AVAILABLE_TOOLS = [
  // One toggle controls both `search` and `extract` in the agent (see search_agent.py normalization)
  { name: "web_search", display_name: "Web Search", description: "Web search + extract" },
]

const SettingsPanel = ({ user, onClose }) => {
  const [activeSection, setActiveSection] = useState('tools') // 'tools', 'apikey', or 'mcp'
  const [mcpServers, setMcpServers] = useState([])
  const [tools, setTools] = useState(() => {
    // Initialize tools from localStorage or default to all enabled
    if (typeof window !== 'undefined' && user?.user_id) {
      const stored = localStorage.getItem(`tools_${user.user_id}`)
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          return AVAILABLE_TOOLS.map(tool => ({
            ...tool,
            enabled: parsed[tool.name] !== false // Default to true if not set
          }))
        } catch (e) {
          console.error('Failed to parse stored tools:', e)
        }
      }
    }
    // Default: all enabled
    return AVAILABLE_TOOLS.map(tool => ({ ...tool, enabled: true }))
  })
  const [loading, setLoading] = useState(false)
  const [editingServer, setEditingServer] = useState(null)
  const [showAddForm, setShowAddForm] = useState(false)
  
  // Form state for new/edit server
  const [formData, setFormData] = useState({
    name: '',
    command: '',
    args: '',
    env: ''
  })

  useEffect(() => {
    if (user && user.user_id) {
      loadMcpServers()
      // Load tools from localStorage
      const stored = localStorage.getItem(`tools_${user.user_id}`)
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          setTools(AVAILABLE_TOOLS.map(tool => ({
            ...tool,
            enabled: parsed[tool.name] !== false
          })))
        } catch (e) {
          console.error('Failed to parse stored tools:', e)
        }
      }
    }
  }, [user])


  const loadMcpServers = async () => {
    if (!user?.user_id) return
    try {
      setLoading(true)
      const response = await axios.get('/api/mcp/servers', {
        params: { user_id: user.user_id }
      })
      setMcpServers(response.data)
    } catch (error) {
      console.error('Failed to load MCP servers:', error)
    } finally {
      setLoading(false)
    }
  }

  const toggleTool = (toolName, enabled) => {
    if (!user?.user_id) return
    
    // Update local state
    setTools(prev => prev.map(tool => 
      tool.name === toolName ? { ...tool, enabled } : tool
    ))
    
    // Save to localStorage
    const toolPrefs = tools.reduce((acc, tool) => {
      acc[tool.name] = tool.name === toolName ? enabled : tool.enabled
      return acc
    }, {})
    localStorage.setItem(`tools_${user.user_id}`, JSON.stringify(toolPrefs))
  }

  const handleAddServer = async () => {
    if (!user?.user_id) return
    
    try {
      // Parse args and env - trim whitespace from each arg
      const args = formData.args.split('\n').map(a => a.trim()).filter(a => a.length > 0)
      let env = null
      if (formData.env.trim()) {
        try {
          env = JSON.parse(formData.env)
        } catch (e) {
          alert('Invalid JSON for environment variables')
          return
        }
      }

      await axios.post('/api/mcp/servers', {
        name: formData.name,
        command: formData.command,
        args: args,
        env: env
      }, {
        params: { user_id: user.user_id }
      })

      // Reset form and reload
      setFormData({ name: '', command: '', args: '', env: '' })
      setShowAddForm(false)
      loadMcpServers()
    } catch (error) {
      console.error('Failed to add MCP server:', error)
      alert('Failed to add MCP server: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleEditServer = async (serverId) => {
    if (!user?.user_id) return
    
    const server = mcpServers.find(s => s.server_id === serverId)
    if (!server) return

    try {
      // Parse args and env - trim whitespace from each arg
      const args = formData.args.split('\n').map(a => a.trim()).filter(a => a.length > 0)
      let env = null
      if (formData.env.trim()) {
        try {
          env = JSON.parse(formData.env)
        } catch (e) {
          alert('Invalid JSON for environment variables')
          return
        }
      }

      // For now, delete and recreate (backend doesn't have update endpoint yet)
      await axios.delete(`/api/mcp/servers/${serverId}`, {
        params: { user_id: user.user_id }
      })

      await axios.post('/api/mcp/servers', {
        name: formData.name,
        command: formData.command,
        args: args,
        env: env
      }, {
        params: { user_id: user.user_id }
      })

      setEditingServer(null)
      setFormData({ name: '', command: '', args: '', env: '' })
      loadMcpServers()
    } catch (error) {
      console.error('Failed to update MCP server:', error)
      alert('Failed to update MCP server: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleDeleteServer = async (serverId) => {
    if (!user?.user_id) return
    if (!confirm('Are you sure you want to delete this MCP server?')) return

    try {
      await axios.delete(`/api/mcp/servers/${serverId}`, {
        params: { user_id: user.user_id }
      })
      loadMcpServers()
    } catch (error) {
      console.error('Failed to delete MCP server:', error)
      alert('Failed to delete MCP server: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleToggleEnabled = async (serverId, enabled) => {
    if (!user?.user_id) return

    try {
      await axios.put(`/api/mcp/servers/${serverId}/enable`, null, {
        params: { 
          user_id: user.user_id,
          enabled: !enabled
        }
      })
      loadMcpServers()
    } catch (error) {
      console.error('Failed to toggle MCP server:', error)
      alert('Failed to toggle MCP server: ' + (error.response?.data?.detail || error.message))
    }
  }

  const startEdit = (server) => {
    setEditingServer(server.server_id)
    setFormData({
      name: server.name,
      command: server.command,
      args: server.args.join('\n'),
      env: server.env ? JSON.stringify(server.env, null, 2) : '',
    })
    setShowAddForm(true)
  }

  const cancelEdit = () => {
    setEditingServer(null)
    setShowAddForm(false)
    setFormData({ name: '', command: '', args: '', env: '' })
  }

  // Toggle section - clicking same section closes it, clicking different opens it
  const toggleSection = (section) => {
    setActiveSection(prev => prev === section ? null : section)
  }

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h3>Settings</h3>
        <button className="settings-close-btn" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div className="settings-accordion">
        {/* Tools Section */}
        <div className={`accordion-section ${activeSection === 'tools' ? 'expanded' : ''}`}>
          <button 
            className="accordion-header"
            onClick={() => toggleSection('tools')}
          >
            <span className="accordion-title">Tools</span>
            <svg 
              className="accordion-arrow" 
              width="16" height="16" viewBox="0 0 24 24" 
              fill="none" stroke="currentColor" strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          {activeSection === 'tools' && (
            <div className="accordion-content">
              {!user || !user.user_id ? (
                <div className="empty-state">
                  <p>Please log in to configure tools.</p>
                </div>
              ) : (
                <>
                  <p className="settings-description">
                    Enable or disable tools available to the agent.
                  </p>
                  {tools.length === 0 ? (
                    <div className="empty-state">
                      <p>No tools available.</p>
                    </div>
                  ) : (
                    <div className="tools-list">
                      {tools.map(tool => (
                        <div key={tool.name} className="tool-item">
                          <div className="tool-info">
                            <div className="tool-name">{tool.display_name}</div>
                            <div className="tool-description">{tool.description}</div>
                          </div>
                          <label className="toggle-switch">
                            <input
                              type="checkbox"
                              checked={tool.enabled}
                              onChange={() => toggleTool(tool.name, !tool.enabled)}
                            />
                            <span className="toggle-slider"></span>
                          </label>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {/* API Key Section */}
        <div className={`accordion-section ${activeSection === 'apikey' ? 'expanded' : ''}`}>
          <button 
            className="accordion-header"
            onClick={() => toggleSection('apikey')}
          >
            <span className="accordion-title">API Key</span>
            <svg 
              className="accordion-arrow" 
              width="16" height="16" viewBox="0 0 24 24" 
              fill="none" stroke="currentColor" strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          {activeSection === 'apikey' && (
            <div className="accordion-content">
              <p className="settings-description">
                Configure your API keys for external services.
              </p>
              <div className="api-key-placeholder">
                <p>API Key configuration coming soon...</p>
              </div>
            </div>
          )}
        </div>

        {/* MCP Section */}
        <div className={`accordion-section ${activeSection === 'mcp' ? 'expanded' : ''}`}>
          <button 
            className="accordion-header"
            onClick={() => toggleSection('mcp')}
          >
            <span className="accordion-title">MCP</span>
            <svg 
              className="accordion-arrow" 
              width="16" height="16" viewBox="0 0 24 24" 
              fill="none" stroke="currentColor" strokeWidth="2"
            >
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
          {activeSection === 'mcp' && (
            <div className="accordion-content">
              {!user || !user.user_id ? (
                <div className="empty-state">
                  <p>Please log in to configure MCP servers.</p>
                </div>
              ) : (
                <>
                  <div className="mcp-header-row">
                    <span className="mcp-subtitle">Configured Servers</span>
                    <button 
                      className="add-server-btn"
                      onClick={() => {
                        cancelEdit()
                        setShowAddForm(true)
                      }}
                    >
                      + Add
                    </button>
                  </div>

                  {showAddForm && (
                    <div className="mcp-server-form">
                      <h5>{editingServer ? 'Edit' : 'Add'} MCP Server</h5>
                      <div className="form-group">
                        <label>Name</label>
                        <input
                          type="text"
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          placeholder="e.g., Filesystem MCP"
                        />
                      </div>
                      <div className="form-group">
                        <label>Command</label>
                        <input
                          type="text"
                          value={formData.command}
                          onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                          placeholder="e.g., npx"
                        />
                      </div>
                      <div className="form-group">
                        <label>Arguments (one per line)</label>
                        <textarea
                          value={formData.args}
                          onChange={(e) => setFormData({ ...formData, args: e.target.value })}
                          placeholder="-y&#10;@modelcontextprotocol/server-filesystem&#10;/path/to/dir"
                          rows={3}
                        />
                      </div>
                      <div className="form-group">
                        <label>Environment Variables (JSON, optional)</label>
                        <textarea
                          value={formData.env}
                          onChange={(e) => setFormData({ ...formData, env: e.target.value })}
                          placeholder='{"KEY": "value"}'
                          rows={3}
                        />
                      </div>
                      <div className="form-actions">
                        <button 
                          className="save-btn"
                          onClick={() => editingServer ? handleEditServer(editingServer) : handleAddServer()}
                        >
                          {editingServer ? 'Update' : 'Add'} Server
                        </button>
                        <button className="cancel-btn" onClick={cancelEdit}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {loading ? (
                    <div className="loading-state">Loading MCP servers...</div>
                  ) : mcpServers.length === 0 && !showAddForm ? (
                    <div className="empty-state">
                      <p>No MCP servers configured.</p>
                      <p className="empty-hint">Click "+ Add" to get started.</p>
                    </div>
                  ) : (
                    <div className="mcp-servers-list">
                      {mcpServers.map(server => (
                        <div key={server.server_id} className="mcp-server-item">
                          <div className="server-header">
                            <div className="server-info">
                              <div className="server-name">{server.name}</div>
                              <div className="server-command">{server.command} {server.args.join(' ')}</div>
                            </div>
                            <div className="server-actions">
                              <label className="toggle-switch">
                                <input
                                  type="checkbox"
                                  checked={server.enabled}
                                  onChange={() => handleToggleEnabled(server.server_id, server.enabled)}
                                />
                                <span className="toggle-slider"></span>
                              </label>
                              <button 
                                className="edit-btn"
                                onClick={() => startEdit(server)}
                                title="Edit"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                                </svg>
                              </button>
                              <button 
                                className="delete-btn"
                                onClick={() => handleDeleteServer(server.server_id)}
                                title="Delete"
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <polyline points="3 6 5 6 21 6"/>
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                                </svg>
                              </button>
                            </div>
                          </div>
                          <div className={`server-status ${server.enabled ? 'enabled' : 'disabled'}`}>
                            {server.enabled ? '✓ Enabled' : '○ Disabled'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SettingsPanel

