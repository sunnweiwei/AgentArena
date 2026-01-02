import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { useTheme } from '../contexts/ThemeContext'
import Sidebar from './Sidebar'
import ChatWindow from './ChatWindow'
import './ChatInterface.css'

const ChatInterface = ({ user, onLogout, onLogin }) => {
  const noop = () => {}
  const { theme, toggleTheme } = useTheme()
  const [chats, setChats] = useState([])
  const [currentChatId, setCurrentChatId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false) // Closed by default
  const [pendingChats, setPendingChats] = useState({})
  const [sharedChat, setSharedChat] = useState(null) // Shared chat data when viewing via share link
  const [shareToken, setShareToken] = useState(null) // Share token from URL
  const [initialMessage, setInitialMessage] = useState(null) // Message to send automatically from URL
  const [isCreatingQueryChat, setIsCreatingQueryChat] = useState(false) // Flag to prevent normal chat loading when creating query chat
  const canUseChat = Boolean(user && user.user_id)

  // Check for share token or query parameter in URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const share = urlParams.get('share')
    const query = urlParams.get('query')
    
    if (share) {
      setShareToken(share)
      // Load shared chat
      axios.get(`/api/shared/${share}`)
        .then(response => {
          setSharedChat(response.data)
          setCurrentChatId(response.data.id)
          setLoading(false)
        })
        .catch(error => {
          console.error('Failed to load shared chat:', error)
          setLoading(false)
        })
    } else if (query && canUseChat) {
      console.log('[ChatInterface] Query parameter detected, creating new chat:', query)
      
      // Set flag to prevent normal chat loading
      setIsCreatingQueryChat(true)
      
      // Create a new chat and send the query message
      const decodedQuery = decodeURIComponent(query)
      
      // Create new chat first
      axios.post('/api/chats', null, {
        params: { user_id: user.user_id }
      })
        .then(response => {
          const newChat = response.data
          console.log('[ChatInterface] New chat created for query:', newChat.id)
          setCurrentChatId(newChat.id)
          localStorage.setItem('lastChatId', newChat.id)
          // Set initial message after chat is created
          setInitialMessage(decodedQuery)
          // Clear the query param from URL AFTER everything is set up
          const newUrl = window.location.pathname
          window.history.replaceState({}, '', newUrl)
          // Clear flag and loading state after everything is set up
          setIsCreatingQueryChat(false)
          setLoading(false)
        })
        .catch(err => {
          console.error('Failed to create chat for query:', err)
          // Clear URL even on error
          const newUrl = window.location.pathname
          window.history.replaceState({}, '', newUrl)
          setIsCreatingQueryChat(false)
          setLoading(false)
        })
    }
  }, [canUseChat, user?.user_id])

  // Check for active streams on mount and update pendingChats
  useEffect(() => {
    if (!canUseChat) return
    
    const checkActiveStreams = async () => {
      try {
        const response = await axios.get('/api/active_streams', {
          params: { user_id: user.user_id }
        })
        const activeStreams = response.data.active_streams || []
        
        // Update pendingChats for all active streams
        if (activeStreams.length > 0) {
          const pendingMap = {}
          activeStreams.forEach(stream => {
            pendingMap[stream.chat_id] = true
          })
          setPendingChats(pendingMap)
          console.log('[ChatInterface] Found active streams:', activeStreams)
        }
      } catch (err) {
        console.error('Failed to check active streams:', err)
      }
    }
    
    checkActiveStreams()
  }, [canUseChat, user?.user_id])

  useEffect(() => {
    // Don't load normal chats if viewing a shared chat
    if (shareToken) {
      return
    }
    
    // Don't load normal chats if there's a query parameter (check URL directly, not state)
    const urlParams = new URLSearchParams(window.location.search)
    if (urlParams.get('query')) {
      console.log('[ChatInterface] Query parameter detected, skipping normal chat loading')
      return
    }
    
    // Don't load normal chats if we're creating a query chat
    if (isCreatingQueryChat) {
      return
    }
    
    if (canUseChat) {
      // Try to restore last selected chat from localStorage
      const savedChatId = localStorage.getItem('lastChatId')
      
      loadChats().then(async (loadedChats) => {
        // If we have a saved chat ID, check if it's an empty chat or has messages
        if (savedChatId) {
          try {
            const response = await axios.get(`/api/chats/${savedChatId}`, {
              params: { user_id: user.user_id }
            })
            
            // If the saved chat has no messages (it's a new/empty chat), keep using it
            if (response.data.messages.length === 0) {
              setCurrentChatId(savedChatId)
            } else if (loadedChats && loadedChats.some(chat => chat.id === savedChatId)) {
              // Saved chat has messages and exists in the list, restore it
              setCurrentChatId(savedChatId)
            } else if (!loadedChats || loadedChats.length === 0) {
              // No chats exist, create a new one
              createNewChat()
            } else {
              // Saved chat doesn't exist anymore, select the most recent chat
              setCurrentChatId(loadedChats[0].id)
            }
          } catch (err) {
            // Saved chat doesn't exist, create a new one or select most recent
            if (!loadedChats || loadedChats.length === 0) {
              createNewChat()
            } else {
              setCurrentChatId(loadedChats[0].id)
            }
          }
        } else if (!loadedChats || loadedChats.length === 0) {
          // No saved chat and no chats exist, create a new one
          createNewChat()
        } else {
          // No saved chat but chats exist, select the most recent
          setCurrentChatId(loadedChats[0].id)
        }
      }).catch((err) => {
        console.error('Error in chat initialization:', err)
        setLoading(false)
      })
    } else {
      setCurrentChatId(null)  // Clear chat when logged out
      setChats([])  // Clear chats
      setLoading(false)
    }
  }, [user, shareToken])

  const loadChats = async () => {
    if (!user || !user.user_id) {
      console.error('Cannot load chats: user or user_id is missing')
      setLoading(false)
      return []
    }
    try {
      const response = await axios.get('/api/chats', {
        params: { user_id: user.user_id }
      })
      // Filter out any empty chats (double-check on frontend)
      const chatsWithMessages = response.data.filter(chat => chat.message_count > 0)
      setChats(chatsWithMessages)
      // If no chats exist, we'll create one after loading
      return chatsWithMessages
    } catch (err) {
      console.error('Failed to load chats:', err)
      return []
    } finally {
      setLoading(false)
    }
  }

  const createNewChat = async () => {
    // If current chat exists and has no messages, reuse it instead of creating new one
    if (currentChatId) {
      try {
        const currentChatResponse = await axios.get(`/api/chats/${currentChatId}`, {
          params: { user_id: user.user_id }
        })
        // If current chat has no messages, just use it
        if (currentChatResponse.data.messages.length === 0) {
          // Only close sidebar on mobile
          if (window.innerWidth <= 768) {
            setSidebarOpen(false)
          }
          return currentChatId
        }
      } catch (err) {
        console.error('Failed to check current chat:', err)
        // Continue to create new chat if check fails
      }
    }

    // Create new chat only if current chat has messages or doesn't exist
    // Note: Don't add to sidebar yet - it will appear automatically when first message is sent
    try {
      const response = await axios.post('/api/chats', null, {
        params: { user_id: user.user_id }
      })
      const newChat = response.data
      // Don't add empty chat to sidebar - it will appear when it has messages
      setCurrentChatId(newChat.id)
      // Save to localStorage so we can restore on page refresh
      localStorage.setItem('lastChatId', newChat.id)
      // Only close sidebar on mobile
      if (window.innerWidth <= 768) {
        setSidebarOpen(false)
      }
      return newChat.id
    } catch (err) {
      console.error('Failed to create chat:', err)
      return null
    }
  }

  const selectChat = (chatId) => {
    setCurrentChatId(chatId)
    // Save to localStorage so we can restore on page refresh
    localStorage.setItem('lastChatId', chatId)
    // Only close sidebar on mobile
    if (window.innerWidth <= 768) {
      setSidebarOpen(false)
    }
  }

  const updateChatTitle = async (chatId, title) => {
    try {
      await axios.put(`/api/chats/${chatId}/title`, null, {
        params: { title, user_id: user.user_id }
      })
      setChats(chats.map(chat => 
        chat.id === chatId ? { ...chat, title } : chat
      ))
    } catch (err) {
      console.error('Failed to update title:', err)
    }
  }

  const refreshChats = () => {
    loadChats().then((loadedChats) => {
      // Chats are already sorted by backend (last user message time)
      // Just update the list - animation will be triggered by Sidebar component
      setChats(loadedChats)
    })
  }

  const handleChatPendingStateChange = useCallback((chatId, isPending) => {
    if (!chatId) return
    setPendingChats(prev => {
      const next = { ...prev }
      if (isPending) {
        next[chatId] = true
      } else {
        delete next[chatId]
      }
      return next
    })
  }, [])

  const handleLogout = () => {
    setCurrentChatId(null)  // Clear current chat
    setChats([])  // Clear chats list
    onLogout()  // Call parent logout handler
  }

  if (loading) {
    return <div className="loading">Loading...</div>
  }

  // If viewing shared chat, show read-only view (no login required)
  if (shareToken && sharedChat) {
    return (
      <div className="chat-interface shared-chat-view">
        <Sidebar
          chats={[]}
          currentChatId={null}
          pendingChats={{}}
          onSelectChat={noop}
          onCreateChat={noop}
          onLogout={noop}
          user={null}
          isOpen={false}
          onToggle={noop}
          theme={theme}
          toggleTheme={toggleTheme}
          isLocked={true}
        />
        <ChatWindow
          chatId={sharedChat.id}
          userId={null} // No user ID for shared chat (read-only)
          sharedChatData={sharedChat} // Pass shared chat data directly
          onUpdateTitle={noop}
          onChatUpdate={noop}
          onCreateChat={noop}
          user={null} // No user required for shared chat
          onLogin={onLogin} // Allow login if user wants to
          sidebarOpen={false}
          onToggleSidebar={noop}
          onChatPendingStateChange={noop}
          isSharedView={true}
        />
      </div>
    )
  }

  return (
    <div className="chat-interface">
      <Sidebar
        chats={canUseChat ? chats : []}
        currentChatId={canUseChat ? currentChatId : null}
        pendingChats={canUseChat ? pendingChats : {}}
        onSelectChat={canUseChat ? selectChat : noop}
        onCreateChat={canUseChat ? createNewChat : noop}
        onLogout={handleLogout}
        user={user}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        theme={theme}
        toggleTheme={toggleTheme}
        isLocked={!canUseChat}
      />
      <ChatWindow
        chatId={currentChatId}
        userId={user?.user_id}
        onUpdateTitle={updateChatTitle}
        onChatUpdate={refreshChats}
        onCreateChat={createNewChat}
        user={user}
        onLogin={onLogin}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onChatPendingStateChange={handleChatPendingStateChange}
        initialMessage={initialMessage}
        onInitialMessageSent={() => setInitialMessage(null)}
      />
    </div>
  )
}

export default ChatInterface

