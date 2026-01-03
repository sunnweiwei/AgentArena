import React, { useState } from 'react'
import './Sidebar.css'

const AdminSidebar = ({ 
  adminUsers, 
  currentChatId, 
  onSelectChat, 
  onLogout, 
  user, 
  isOpen, 
  onToggle,
  theme,
  toggleTheme
}) => {
  const [expandedUsers, setExpandedUsers] = useState({})
  const MAX_CHATS_PER_USER = 5

  const toggleUserExpanded = (userId) => {
    setExpandedUsers(prev => ({
      ...prev,
      [userId]: !prev[userId]
    }))
  }

  return (
    <div className={`sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-header">
        <button className="sidebar-toggle" onClick={onToggle}>
          {isOpen ? '←' : '→'}
        </button>
        {isOpen && (
          <div className="sidebar-title">
            <h2>Admin Panel</h2>
            <span className="admin-badge">🔑</span>
          </div>
        )}
      </div>

      {isOpen && (
        <>
          <div className="user-info">
            <div className="user-email">{user?.email || user?.user_id}</div>
            <div className="user-actions">
              <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
                {theme === 'dark' ? '☀️' : '🌙'}
              </button>
              <button className="logout-btn" onClick={onLogout}>Logout</button>
            </div>
          </div>

          <div className="sidebar-main">
            <div className="admin-users-list">
            {adminUsers.map((userData) => {
              const isExpanded = expandedUsers[userData.user_id]
              const displayedChats = isExpanded 
                ? userData.chats 
                : userData.chats.slice(0, MAX_CHATS_PER_USER)
              const hasMore = userData.chats.length > MAX_CHATS_PER_USER

              return (
                <div key={userData.user_id} className="admin-user-group">
                  <div className="admin-user-header">
                    <div className="admin-user-info">
                      <span className="user-icon">👤</span>
                      <span className="user-email-short">
                        {userData.user_email.split('@')[0]}
                      </span>
                      <span className="chat-count-badge">
                        {userData.chats.length}
                      </span>
                    </div>
                    {hasMore && (
                      <button 
                        className="expand-toggle"
                        onClick={() => toggleUserExpanded(userData.user_id)}
                      >
                        {isExpanded ? '▼' : '▶'}
                      </button>
                    )}
                  </div>

                  <div className="admin-user-chats">
                    {displayedChats.map((chat) => (
                      <div
                        key={chat.id}
                        className={`chat-item ${currentChatId === chat.id ? 'active' : ''}`}
                        onClick={() => onSelectChat(chat.id)}
                      >
                        <div className="chat-title">
                          {chat.title || 'Untitled Chat'}
                        </div>
                        <div className="chat-meta">
                          <span className="chat-message-count">
                            {chat.message_count} msgs
                          </span>
                          {chat.has_survey && (
                            <span className="survey-badge">📋</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {hasMore && !isExpanded && (
                    <div className="show-more-hint" onClick={() => toggleUserExpanded(userData.user_id)}>
                      +{userData.chats.length - MAX_CHATS_PER_USER} more...
                    </div>
                  )}
                </div>
              )
            })}

            {adminUsers.length === 0 && (
              <div className="empty-state">No users with chats yet</div>
            )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default AdminSidebar
