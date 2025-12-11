import React, { useState, useEffect, useRef, useCallback } from 'react'
import axios from 'axios'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import './ChatWindow.css'

const isDev = import.meta.env.DEV

const extractChunkText = (content) => {
  if (!content) return ''
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content.map(part => {
      if (typeof part === 'string') return part
      if (part?.text) return part.text
      if (part?.content) return part.content
      return ''
    }).join('')
  }
  if (typeof content === 'object' && content.text) {
    return content.text
  }
  return String(content)
}

const ChatWindow = ({
  chatId,
  userId,
  onUpdateTitle,
  onChatUpdate,
  onCreateChat,
  user,
  onLogin,
  sidebarOpen,
  onToggleSidebar,
  onChatPendingStateChange
}) => {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [connectionNotice, setConnectionNotice] = useState('')
  const [selectedModel, setSelectedModel] = useState('Auto')
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)

  const wsRef = useRef(null)
  const activeChatRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const connectionTimeoutRef = useRef(null)
  const requestIdRef = useRef(0)
  const onUpdateTitleRef = useRef(onUpdateTitle)
  const onChatUpdateRef = useRef(onChatUpdate)
  const modelSelectorRef = useRef(null)
  const streamingMessageIdRef = useRef(null)
  const streamIdToMessageIdRef = useRef({})
  const streamBuffersRef = useRef({})
  const pendingOutgoingMessagesRef = useRef([])
  const pendingWaitingMessageIdsRef = useRef([])
  const fetchMessagesRef = useRef(async () => {})
  const pendingStreamMetaRef = useRef({})
  const generateClientIdRef = useRef(0)
  const generateClientId = useCallback(() => {
    generateClientIdRef.current += 1
    return `msg-${Date.now()}-${generateClientIdRef.current}-${Math.random().toString(16).slice(2)}`
  }, [])
  const normalizeMessages = useCallback(
    (incoming = [], sourceChatId = chatId) =>
      incoming.map((message) => {
        const hasServerId = message.id !== undefined && message.id !== null
        return {
          ...message,
          chatId: message.chatId ?? sourceChatId ?? null,
          clientId: message.clientId || (hasServerId ? `server-${message.id}` : generateClientId()),
          isLoading: Boolean(message.isLoading)
        }
      }),
    [generateClientId, chatId]
  )

  useEffect(() => {
    onUpdateTitleRef.current = onUpdateTitle
  }, [onUpdateTitle])

  useEffect(() => {
    onChatUpdateRef.current = onChatUpdate
  }, [onChatUpdate])

  const resolvePendingStream = useCallback((chatKey) => {
    if (!chatKey) return
    const pendingMeta = pendingStreamMetaRef.current[chatKey]
    if (pendingMeta && pendingMeta.waitingId && activeChatRef.current === chatKey) {
      setMessages(prev =>
        prev.filter(msg => !(msg.id === pendingMeta.waitingId && msg.isLoading && msg.role === 'assistant'))
      )
    }
    if (pendingMeta) {
      onChatPendingStateChange?.(chatKey, false)
    }
    delete pendingStreamMetaRef.current[chatKey]
  }, [onChatPendingStateChange])

  const applyPendingPlaceholder = useCallback((chatKey, baseMessages) => {
    if (!chatKey) {
      return baseMessages
    }
    const cleaned = baseMessages.filter(msg => !(msg.role === 'assistant' && msg.isLoading && msg.isOptimistic))
    const pendingMeta = pendingStreamMetaRef.current[chatKey]
    if (!pendingMeta) {
      return cleaned
    }
    const placeholderId = pendingMeta.waitingId || generateClientId()
    const placeholder = {
      id: placeholderId,
      clientId: placeholderId,
      chatId: chatKey,
      role: 'assistant',
      content: '',
      isLoading: true,
      isOptimistic: true,
      created_at: pendingMeta.createdAt || new Date().toISOString()
    }
    pendingStreamMetaRef.current[chatKey] = {
      waitingId: placeholderId,
      createdAt: placeholder.created_at
    }
    return [...cleaned, placeholder]
  }, [generateClientId])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (modelSelectorRef.current && !modelSelectorRef.current.contains(event.target)) {
        setModelSelectorOpen(false)
      }
    }

    if (modelSelectorOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [modelSelectorOpen])

  const flushPendingMessages = useCallback(() => {
    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    while (pendingOutgoingMessagesRef.current.length > 0) {
      const payload = pendingOutgoingMessagesRef.current.shift()
      try {
        socket.send(JSON.stringify(payload))
      } catch (err) {
        console.error('Failed to send queued message:', err)
        pendingOutgoingMessagesRef.current.unshift(payload)
        setConnectionNotice('Connection issue, retrying send…')
        return
      }
    }
    setConnectionNotice('')
  }, [])

  const handleSocketMessage = useCallback((data) => {
    const targetChatId = data.chat_id
    const currentChatId = activeChatRef.current
    const resolvedChatId = targetChatId || currentChatId
    const isCurrentChat = !targetChatId || targetChatId === currentChatId

    if (!isCurrentChat) {
      if ((data.type === 'message' && data.role === 'assistant') || data.type === 'message_complete' || data.type === 'error') {
        resolvePendingStream(targetChatId)
      }
      if (data.type === 'message' || data.type === 'message_complete') {
        onChatUpdateRef.current?.()
      }
      return
    }

    if (data.type === 'message') {
      setMessages(prev => {
        if (prev.some(m => m.id === data.id)) {
          if (isDev) {
            console.log('[WS message] Message already exists, skipping:', data.id)
          }
          return prev
        }

        if (data.role === 'assistant') {
          const assistantText = extractChunkText(data.content)
          resolvePendingStream(resolvedChatId ?? currentChatId)
          const waitingMsg = prev.find(m => m.isLoading)
          if (waitingMsg) {
            const queueIndex = pendingWaitingMessageIdsRef.current.indexOf(waitingMsg.id)
            if (queueIndex !== -1) {
              pendingWaitingMessageIdsRef.current.splice(queueIndex, 1)
            }
            streamingMessageIdRef.current = null
            streamIdToMessageIdRef.current = {}
              return prev.map(m => {
                if (m.id === waitingMsg.id) {
                  return {
                    ...m,
                    id: data.id,
                  chatId: resolvedChatId ?? m.chatId ?? currentChatId,
                    role: data.role,
                    clientId: m.clientId || waitingMsg.id,
                    content: assistantText,
                    created_at: data.created_at,
                    isLoading: false,
                    isOptimistic: false
                  }
                }
                return m
              })
          }
          streamingMessageIdRef.current = null
          streamIdToMessageIdRef.current = {}
          return [
            ...prev,
            {
              id: data.id,
              chatId: resolvedChatId ?? currentChatId,
              clientId: `server-${data.id}`,
              role: data.role,
              content: assistantText,
              created_at: data.created_at,
              isLoading: false
            }
          ]
        }

        if (data.role === 'user') {
          const tempUserMsg = prev.find(
            m => m.isOptimistic && m.role === 'user' && m.content === data.content
          )
          if (tempUserMsg) {
            return prev.map(m => {
              if (m.id === tempUserMsg.id) {
                    return {
                      ...m,
                      id: data.id,
                  chatId: resolvedChatId ?? m.chatId ?? currentChatId,
                      clientId: m.clientId || `server-${data.id}`,
                      created_at: data.created_at,
                      isOptimistic: false
                    }
              }
              return m
            })
          }
        }

        return [
          ...prev,
          {
            id: data.id,
            chatId: resolvedChatId ?? currentChatId,
            clientId: `server-${data.id}`,
            role: data.role,
            content: data.content,
            created_at: data.created_at,
            isLoading: false
          }
        ]
      })

      if (data.role === 'user') {
        onChatUpdateRef.current?.()
      }
    } else if (data.type === 'message_start') {
      const streamId = data.stream_id || `stream-${Date.now()}`
      streamingMessageIdRef.current = streamId
      streamBuffersRef.current[streamId] = { chunks: [], text: '' }
      if (isDev) {
        console.log('[WS message_start]', 'streamId:', streamId, 'pending queue:', pendingWaitingMessageIdsRef.current)
      }
      setMessages(prev => {
        let waitingMsg = null
        if (pendingWaitingMessageIdsRef.current.length > 0) {
          const candidateId = pendingWaitingMessageIdsRef.current[0]
          waitingMsg = prev.find(m => m.id === candidateId)
          if (waitingMsg) {
            pendingWaitingMessageIdsRef.current.shift()
          }
        }

        if (!waitingMsg) {
          waitingMsg = prev.find(m => m.isLoading)
        }

        if (waitingMsg) {
          streamIdToMessageIdRef.current[streamId] = waitingMsg.id
          if (isDev) {
            console.log('[WS message_start]', 'Binding stream to waiting message:', streamId, waitingMsg.id)
          }
          return prev.map(m => m.id === waitingMsg.id ? {
            ...m,
            isLoading: true,
            role: 'assistant',
            content: m.content || '',
            isOptimistic: true,
            chatId: currentChatId ?? m.chatId ?? null
          } : m)
        }

        const fallbackId = streamIdToMessageIdRef.current[streamId] || streamId
        streamIdToMessageIdRef.current[streamId] = fallbackId
        if (prev.some(m => m.id === fallbackId)) {
          return prev
        }
        if (isDev) {
          console.log('[WS message_start]', 'Creating fallback assistant message for stream:', streamId, 'with id:', fallbackId)
        }
        return [
          ...prev,
          {
            id: fallbackId,
            clientId: fallbackId,
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            isLoading: true,
            isOptimistic: true,
            chatId: currentChatId ?? null
          }
        ]
      })
    } else if (data.type === 'message_chunk') {
      const chunkText = extractChunkText(data.content)
      const streamId = data.stream_id || streamingMessageIdRef.current
      if (!chunkText || !streamId) return
      if (isDev) {
        console.log('[WS chunk]', chunkText, 'streamId:', streamId, 'map:', streamIdToMessageIdRef.current)
      }
      const chunkIndex = typeof data.chunk_index === 'number' ? data.chunk_index : null
      const targetId = streamIdToMessageIdRef.current[streamId] || streamId
      streamIdToMessageIdRef.current[streamId] = targetId

      const buffer = streamBuffersRef.current[streamId] || { chunks: [], text: '' }
      if (chunkIndex !== null) {
        buffer.chunks = buffer.chunks.filter(c => c.index !== chunkIndex)
        buffer.chunks.push({ index: chunkIndex, text: chunkText })
        buffer.chunks.sort((a, b) => a.index - b.index)
        buffer.text = buffer.chunks.map(c => c.text).join('')
      } else {
        buffer.text = (buffer.text || '') + chunkText
      }
      streamBuffersRef.current[streamId] = buffer
      const mergedText = buffer.text || chunkText

      setMessages(prev => {
        let found = false
        const updated = prev.map(msg => {
          if (msg.id === targetId) {
            found = true
            if (isDev) {
              console.log('[WS chunk] Updating message:', msg.id, 'old length:', msg.content?.length || 0, 'chunk length:', chunkText.length)
            }
            return {
              ...msg,
              role: 'assistant',
              isLoading: false,
              content: mergedText,
              isOptimistic: false,
              chatId: msg.chatId ?? currentChatId ?? null
            }
          }
          return msg
        })

        if (!found) {
          if (isDev) {
            console.log('[WS chunk] Creating new assistant message for stream:', streamId, 'targetId:', targetId)
          }
          return [
            ...prev,
            {
              id: targetId,
              clientId: targetId,
              role: 'assistant',
              isLoading: false,
              content: mergedText,
              created_at: new Date().toISOString(),
              isOptimistic: false,
              chatId: currentChatId ?? null
            }
          ]
        }

        return updated
      })
      resolvePendingStream(currentChatId)
    } else if (data.type === 'message_complete') {
      const finalText = extractChunkText(data.content)
      const streamId = data.stream_id || streamingMessageIdRef.current
      const targetId = streamId ? (streamIdToMessageIdRef.current[streamId] || streamId) : null
      if (isDev) {
        console.log('[WS message_complete]', 'streamId:', streamId, 'target:', targetId, 'final length:', finalText.length)
      }
      if (!targetId) {
        streamingMessageIdRef.current = null
        resolvePendingStream(currentChatId)
        onChatUpdateRef.current?.()
        fetchMessagesRef.current({ showLoader: false })
        return
      }
      setMessages(prev => {
        let updatedFlag = false
        if (prev.some(m => m.id === data.id)) {
          if (isDev) {
            console.log('[WS message_complete] Message with final ID already exists, skipping update')
          }
          return prev
        }
        const updated = prev.map(msg => {
          if (msg.id === targetId) {
            updatedFlag = true
            if (isDev) {
              console.log('[WS message_complete] Updating message ID from', targetId, 'to', data.id)
            }
            return {
              ...msg,
              id: data.id,
              clientId: msg.clientId || `server-${data.id}`,
              role: data.role,
              isLoading: false,
              created_at: data.created_at,
              content: finalText || msg.content || '',
              isOptimistic: false,
              chatId: resolvedChatId ?? msg.chatId ?? currentChatId ?? null
            }
          }
          return msg
        })
        if (!updatedFlag) {
          if (isDev) {
            console.log('[WS message_complete] Message not found, appending new one for stream:', streamId)
          }
          return [
            ...prev,
            {
              id: data.id,
              clientId: `server-${data.id}`,
              role: data.role,
              content: finalText,
              created_at: data.created_at,
              chatId: resolvedChatId ?? currentChatId ?? null
            }
          ]
        }
        return updated
      })
      if (streamId) {
        delete streamIdToMessageIdRef.current[streamId]
        delete streamBuffersRef.current[streamId]
      }
      streamingMessageIdRef.current = null
      resolvePendingStream(resolvedChatId ?? currentChatId)
      onChatUpdateRef.current?.()
      fetchMessagesRef.current({ showLoader: false })
    } else if (data.type === 'error') {
      console.error('Server error:', data.message)
      setConnectionNotice(data.message || 'An error occurred')
      const streamId = data.stream_id
      if (streamId && streamIdToMessageIdRef.current[streamId]) {
        const targetId = streamIdToMessageIdRef.current[streamId]
        setMessages(prev => prev.filter(m => m.id !== targetId))
        delete streamIdToMessageIdRef.current[streamId]
      } else {
        setMessages(prev => prev.filter(m => !m.isLoading))
      }
      streamingMessageIdRef.current = null
      resolvePendingStream(currentChatId)
      pendingWaitingMessageIdsRef.current = []
    }
  }, [resolvePendingStream])

  useEffect(() => {
    activeChatRef.current = chatId ?? null
    setConnectionNotice('')
    streamIdToMessageIdRef.current = {}
    streamBuffersRef.current = {}
    pendingWaitingMessageIdsRef.current = []
    streamingMessageIdRef.current = null
    setMessages([])

    if (!chatId || !userId) {
      fetchMessagesRef.current = async () => {}
      return
    }

    let isCurrent = true
    const requestId = ++requestIdRef.current

    const fetchMessages = async ({ showLoader = true } = {}) => {
      if (showLoader) {
        setLoading(true)
      }
      try {
        const response = await axios.get(`/api/chats/${chatId}`, {
          params: { user_id: userId }
        })

        if (!isCurrent || activeChatRef.current !== chatId || requestId !== requestIdRef.current) {
          return
        }

        const uniqueMessages = response.data.messages.reduce((acc, msg) => {
          if (!acc.some(m => m.id === msg.id)) {
            acc.push(msg)
          }
          return acc
  }, [resolvePendingStream])
        uniqueMessages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        setMessages((prev) => {
          const normalized = normalizeMessages(uniqueMessages.map((msg) => ({ ...msg, chatId })), chatId)
          const placeholders = prev.filter((msg) => {
            const isTempId = typeof msg.id === 'string' && msg.id.startsWith('msg-')
            return msg.chatId === chatId && (msg.isLoading || (isTempId && msg.isOptimistic))
          })

          const filteredPlaceholders = placeholders.filter((placeholder) => {
            return !normalized.some(
              (msg) =>
                msg.id === placeholder.id ||
                msg.clientId === placeholder.clientId
            )
          })

          const combined = [...normalized, ...filteredPlaceholders]
          return applyPendingPlaceholder(chatId, combined)
        })

        if (response.data.title === 'New Chat' && response.data.messages.length > 0) {
          const firstUserMessage = response.data.messages.find(m => m.role === 'user')
          if (firstUserMessage) {
            const truncated = firstUserMessage.content.slice(0, 50)
            onUpdateTitleRef.current?.(chatId, truncated.length === firstUserMessage.content.length ? truncated : `${truncated}...`)
          }
        }
      } catch (err) {
        if (isCurrent) {
          console.error('Failed to load messages:', err)
        }
      } finally {
        if (isCurrent && showLoader) {
          setLoading(false)
        }
      }
    }

    fetchMessagesRef.current = fetchMessages
    fetchMessages()

    return () => {
      isCurrent = false
    }
  }, [chatId, userId])

  useEffect(() => {
    if (!userId) {
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (err) {
          console.error('Error closing socket:', err)
        }
        wsRef.current = null
      }
      setConnected(false)
      return
    }

    let isAlive = true

    const connectSocket = () => {
      if (!isAlive) return
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsHost = window.location.host
      const socket = new WebSocket(`${wsProtocol}//${wsHost}/ws/${userId}`)
      wsRef.current = socket
      console.log('Opening WebSocket:', `${wsProtocol}//${wsHost}/ws/${userId}`)

      connectionTimeoutRef.current = setTimeout(() => {
        if (socket.readyState === WebSocket.CONNECTING) {
          console.warn('WebSocket connection timeout, closing and retrying…')
          socket.close()
        }
        connectionTimeoutRef.current = null
      }, 5000)

      socket.onopen = () => {
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current)
          connectionTimeoutRef.current = null
        }
        if (!isAlive) {
          socket.close()
          return
        }
        setConnected(true)
        setConnectionNotice('')
        flushPendingMessages()
        console.log('WebSocket connected successfully')
      }

      socket.onmessage = (event) => {
        if (!isAlive) return
        const data = JSON.parse(event.data)
        if (isDev) {
          console.log('[WS]', data)
        }
        handleSocketMessage(data)
      }

      socket.onerror = (error) => {
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current)
          connectionTimeoutRef.current = null
        }
        console.error('WebSocket error:', error)
        if (!isAlive) return
        setConnectionNotice('Connection error. Reconnecting…')
        setConnected(false)
      }

      socket.onclose = (event) => {
        if (connectionTimeoutRef.current) {
          clearTimeout(connectionTimeoutRef.current)
          connectionTimeoutRef.current = null
        }
        if (!isAlive) return
        wsRef.current = null
        setConnected(false)
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null
          connectSocket()
        }, 1000)
      }
    }

    connectSocket()

    return () => {
      isAlive = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (connectionTimeoutRef.current) {
        clearTimeout(connectionTimeoutRef.current)
        connectionTimeoutRef.current = null
      }
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (err) {
          console.error('Error closing socket on cleanup:', err)
        }
        wsRef.current = null
      }
    }
  }, [userId, flushPendingMessages, handleSocketMessage])

  useEffect(() => {
    if (!chatId || !userId) return
    const interval = setInterval(() => {
      fetchMessagesRef.current({ showLoader: false })
    }, connected ? 12000 : 4000)
    return () => clearInterval(interval)
  }, [connected, chatId, userId])

  const sendMessage = async (content) => {
    const trimmed = content.trim()
    if (!trimmed) return

    if (!chatId) {
      console.warn('No active chat to send message')
      return
    }

    const tempId = generateClientId()
    const clientId = tempId
    setMessages(prev => [
      ...prev,
      {
        id: tempId,
        clientId,
        chatId,
        role: 'user',
        content: trimmed,
        created_at: new Date().toISOString(),
        isOptimistic: true
      }
    ])

    const waitingId = generateClientId()
    streamingMessageIdRef.current = waitingId
    pendingWaitingMessageIdsRef.current.push(waitingId)
    setMessages(prev => [
      ...prev,
      {
        id: waitingId,
        clientId: waitingId,
        chatId,
        role: 'assistant',
        content: '',
        isLoading: true,
        isOptimistic: true,
        created_at: new Date().toISOString()
      }
    ])

    const payload = {
      type: 'message',
      chat_id: chatId,
      content: trimmed,
      model: selectedModel
    }

    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      pendingOutgoingMessagesRef.current.push(payload)
      setConnectionNotice('Connecting… message will send automatically')
      pendingStreamMetaRef.current[chatId] = {
        waitingId,
        createdAt: new Date().toISOString()
      }
      onChatPendingStateChange?.(chatId, true)
      return
    }

    pendingStreamMetaRef.current[chatId] = {
      waitingId,
      createdAt: new Date().toISOString()
    }
    onChatPendingStateChange?.(chatId, true)

    try {
      if (isDev) {
        console.log('[WS send]', payload)
      }
      socket.send(JSON.stringify(payload))
    } catch (err) {
      console.error('Failed to send message:', err)
      setConnectionNotice('Unable to send message. Connection issue.')
      onChatPendingStateChange?.(chatId, false)
      delete pendingStreamMetaRef.current[chatId]
      setMessages(prev => prev.filter(msg => msg.id !== tempId && msg.id !== waitingId))
    }
  }

  const handleLogin = async (username) => {
    if (!username || !username.trim()) return
    try {
      const response = await axios.post('/api/auth/login', {
        email: username.trim()
      })
      if (response.data && response.data.user_id) {
        onLogin(response.data)
      } else {
        console.error('Invalid login response:', response.data)
      }
    } catch (err) {
      console.error('Login failed:', err)
    }
  }

  const models = ['Auto', 'GPT-5-Nano', 'GPT-5-Mini']

  const renderModelSelector = () => (
    <div className="model-selector-container" ref={modelSelectorRef}>
      <button
        className="model-selector-button"
        onClick={() => setModelSelectorOpen(!modelSelectorOpen)}
        title="Select model"
      >
        <span className="model-selector-label">{selectedModel}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`model-selector-arrow ${modelSelectorOpen ? 'open' : ''}`}
        >
          <polyline points="6 9 12 15 18 9"></polyline>
        </svg>
      </button>
      {modelSelectorOpen && (
        <div className="model-selector-dropdown">
          {models.map((model) => (
            <button
              key={model}
              className={`model-option ${selectedModel === model ? 'selected' : ''}`}
              onClick={() => {
                setSelectedModel(model)
                setModelSelectorOpen(false)
              }}
            >
              {model}
              {selectedModel === model && (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )

  if (!user) {
    return (
      <div className="chat-window">
        <div className="chat-header">
          <button className="menu-button" onClick={onToggleSidebar} title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <rect x="4" y="5" width="16" height="14" rx="2" ry="2" />
              <line x1="9" y1="5" x2="9" y2="19" />
            </svg>
          </button>
          {renderModelSelector()}
          <div className="chat-status">
            <span className="status-indicator disconnected">● Please log in</span>
          </div>
        </div>
        <div className="chat-body login-state">
          <div className="prelogin-messages">
            <span className="placeholder-label">Preview</span>
            <div className="placeholder-message user" />
            <div className="placeholder-message assistant" />
            <div className="placeholder-message user short" />
            <div className="placeholder-message assistant long" />
          </div>
          <div className="login-overlay">
            <div className="login-overlay-card">
              <h2>Welcome to Chat</h2>
              <p>Sign in to continue your conversations</p>
              <div className="login-input-wrapper">
                <input
                  type="text"
                  placeholder="Enter username"
                  className="login-input-inline"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && e.target.value.trim()) {
                      handleLogin(e.target.value)
                    }
                  }}
                  autoFocus
                />
                <button
                  className="login-button-inline"
                  onClick={(e) => {
                    const input = e.target.previousElementSibling
                    if (input && input.value.trim()) {
                      handleLogin(input.value)
                    }
                  }}
                >
                  Continue
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!chatId && user) {
    return (
      <div className="chat-window">
        <div className="chat-header">
          <button className="menu-button" onClick={onToggleSidebar} title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <rect x="4" y="5" width="16" height="14" rx="2" ry="2" />
              <line x1="9" y1="5" x2="9" y2="19" />
            </svg>
          </button>
          {renderModelSelector()}
          <div className="chat-status"></div>
        </div>
        <div className="chat-body">
          <MessageList messages={[]} />
        </div>
        <MessageInput onSendMessage={sendMessage} disabled />
      </div>
    )
  }

  return (
    <div className="chat-window">
      <div className="chat-header">
        <button className="menu-button" onClick={onToggleSidebar} title={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            <rect x="4" y="5" width="16" height="14" rx="2" ry="2" />
            <line x1="9" y1="5" x2="9" y2="19" />
          </svg>
        </button>
        {renderModelSelector()}
        <div className="chat-status">
          {connected ? (
            <span className="status-indicator connected">● Connected</span>
          ) : (
            <span className="status-indicator disconnected">● Connecting...</span>
          )}
        </div>
      </div>
      <div className="chat-body">
        {connectionNotice && (
          <div className="connection-notice">
            {connectionNotice}
          </div>
        )}
        {loading ? (
          <div className="loading-messages">Loading messages...</div>
        ) : (
          <MessageList messages={messages} />
        )}
      </div>
      <MessageInput onSendMessage={sendMessage} disabled={!chatId} />
    </div>
  )
}

export default ChatWindow
