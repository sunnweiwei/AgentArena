import React, { useState, useEffect, useRef } from 'react'
import './Sidebar.css'

const Sidebar = ({ 
  chats, 
  currentChatId, 
  pendingChats = {},
  onSelectChat, 
  onCreateChat, 
  onLogout, 
  user,
  isOpen,
  onToggle,
  theme,
  toggleTheme,
  isLocked = false
}) => {
  const [animatingChatId, setAnimatingChatId] = useState(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef(null)

  // Trigger animation when a chat moves to top
  useEffect(() => {
    if (currentChatId && chats.length > 0 && chats[0].id === currentChatId) {
      setAnimatingChatId(currentChatId)
      const timer = setTimeout(() => {
        setAnimatingChatId(null)
      }, 400)
      return () => clearTimeout(timer)
    }
  }, [chats, currentChatId])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setUserMenuOpen(false)
      }
    }
    if (userMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [userMenuOpen])

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && <div className="sidebar-overlay" onClick={onToggle} />}
      
      <div 
        className={`sidebar ${isOpen ? 'open' : ''} ${isLocked ? 'locked' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sidebar-header">
          <button 
            className="new-chat-button" 
            onClick={() => {
              if (isLocked) return
              onCreateChat?.()
            }}
            disabled={isLocked}
            title={isLocked ? 'Login to start chatting' : 'Start a new chat'}
          >
            <span>+</span> New Chat
          </button>
        </div>

        <div className="chat-list">
          {isLocked ? (
            <div className="empty-state">
              Log in to see your chats.
            </div>
          ) : chats.length === 0 ? (
            <div className="empty-state">
              No chats yet. Start a new conversation!
            </div>
          ) : (
            chats.map(chat => {
              const isPending = Boolean(pendingChats?.[chat.id])
              return (
                <div
                  key={chat.id}
                  className={`chat-item ${chat.id === currentChatId ? 'active' : ''} ${animatingChatId === chat.id ? 'moving-to-top' : ''} ${isPending ? 'pending' : ''}`}
                  onClick={() => {
                    if (isLocked) return
                    onSelectChat(chat.id)
                  }}
                >
                  <div className="chat-item-content">
                    <div className="chat-title-row">
                      <div className="chat-title">{chat.title}</div>
                      {isPending && (
                        <div className="chat-pending-indicator" title="Assistant response in progress">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>

        <div className="sidebar-footer" ref={userMenuRef}>
          {user && (
            <>
              <button
                className="user-summary-button"
                onClick={() => setUserMenuOpen(prev => !prev)}
                title="Open user menu"
              >
                <div className="user-avatar">
                  {user.email ? user.email.charAt(0).toUpperCase() : 'U'}
                </div>
                <div className="user-info">
                  <div className="user-email">{user.email}</div>
                </div>
              </button>
              <button className="theme-toggle-button" onClick={toggleTheme} title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
                {theme === 'dark' ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="5"/>
                    <line x1="12" y1="1" x2="12" y2="3"/>
                    <line x1="12" y1="21" x2="12" y2="23"/>
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                    <line x1="1" y1="12" x2="3" y2="12"/>
                    <line x1="21" y1="12" x2="23" y2="12"/>
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  </svg>
                )}
              </button>
              <button className="logout-button" onClick={onLogout} title="Logout">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
              </button>
              {userMenuOpen && (
                <div className="user-menu-dropdown">
                  <button className="user-menu-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="3"/>
                      <path d="M12 1v6m0 6v6m5.2-13.2l-4.2 4.2m-2 2l-4.2 4.2M23 12h-6m-6 0H5m13.2 5.2l-4.2-4.2m-2-2l-4.2-4.2"/>
                    </svg>
                    Settings
                  </button>
                  <button className="user-menu-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="7" width="20" height="14" rx="2"/>
                      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
                    </svg>
                    MCP
                  </button>
                  <button className="user-menu-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>
                    </svg>
                    API Key
                  </button>
                  <button className="user-menu-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3m.08 4h.01"/>
                    </svg>
                    Get help
                  </button>
                  <button className="user-menu-item">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                    </svg>
                    Learn more
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}

export default Sidebar

