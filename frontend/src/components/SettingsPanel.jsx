import React from 'react'
import './SettingsPanel.css'

const SettingsPanel = ({ user, onClose }) => {
  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h2>Settings</h2>
        <button className="close-button" onClick={onClose} title="Close settings">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      
      <div className="settings-content">
        {user && (
          <div className="settings-section">
            <h3>User Information</h3>
            <div className="settings-item">
              <label>Email:</label>
              <span>{user.email || 'Not available'}</span>
            </div>
            {user.id && (
              <div className="settings-item">
                <label>User ID:</label>
                <span>{user.id}</span>
              </div>
            )}
          </div>
        )}
        
        <div className="settings-section">
          <h3>About</h3>
          <p>AgentArena Chat Interface</p>
        </div>
      </div>
    </div>
  )
}

export default SettingsPanel

