import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import SurveyModal from './SurveyModal'
import { getLastCanvasContent, DiffBlock, extractCanvasContent } from './AgentBlock'
import './ChatWindow.css'

const isDev = import.meta.env.DEV

// Canvas display component - shows the last canvas content from messages
const CanvasDisplay = ({ messages }) => {
  const canvasContent = useMemo(() => {
    return getLastCanvasContent(messages)
  }, [messages])

  if (!canvasContent) {
    return (
      <div className="canvas-empty">
        <p>Canvas content will appear here</p>
      </div>
    )
  }

  return (
    <div className="canvas-content">
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]}
        components={{
          code: ({node, inline, className, children, ...props}) => {
            const match = /language-(\w+)/.exec(className || '')
            const language = match ? match[1] : ''
            const content = String(children).replace(/\n$/, '')
            
            if (!inline && (language === 'diff' || language === 'patch')) {
              return <DiffBlock content={content} />
            }
            
            // Default code rendering
            return inline ? (
              <code className={className} {...props}>{children}</code>
            ) : (
              <code className={className} {...props}>{children}</code>
            )
          },
          a: ({node, href, children, ...props}) => (
            <a 
              href={href} 
              onClick={(e) => {
                e.preventDefault()
                // Open in a smaller popup window
                const width = Math.min(1200, window.screen.width * 0.7)
                const height = Math.min(800, window.screen.height * 0.8)
                const left = (window.screen.width - width) / 2
                const top = (window.screen.height - height) / 2
                window.open(href, '_blank', `width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes`)
              }}
              {...props} 
              style={{color: '#0066cc', textDecoration: 'underline', cursor: 'pointer'}}
            >
              {children}
            </a>
          )
        }}
      >
        {canvasContent}
      </ReactMarkdown>
    </div>
  )
}

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
  onChatPendingStateChange,
  onSurveyRequested,
  sharedChatData = null,
  isSharedView = false
}) => {
  // Notify parent about streaming status changes
  const notifyStreamingStatus = useCallback((isStreaming) => {
    if (chatId && onChatPendingStateChange) {
      onChatPendingStateChange(chatId, isStreaming)
    }
  }, [chatId, onChatPendingStateChange])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [connected, setConnected] = useState(false)
  const [connectionNotice, setConnectionNotice] = useState('')
  const [selectedModel, setSelectedModel] = useState('Auto')
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false)
  const [metaInfo, setMetaInfo] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [canvasOpen, setCanvasOpen] = useState(false)
  const [shareUrl, setShareUrl] = useState(null)
  const [shareCopied, setShareCopied] = useState(false)
  const [showShareNotification, setShowShareNotification] = useState(false)
  const [splitRatio, setSplitRatio] = useState(50) // Percentage for left panel
  const [isDragging, setIsDragging] = useState(false)

  // Survey state
  const [showSurvey, setShowSurvey] = useState(false)
  const [surveyForChatId, setSurveyForChatId] = useState(null)
  const [chatMetaInfo, setChatMetaInfo] = useState('')

  const activeStreamIdRef = useRef(null)

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
  const lastSubscribeChatIdRef = useRef(null)
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
          // CRITICAL: Messages from database should NEVER have loading/streaming flags
          // Always set them to false explicitly
          isLoading: false,
          isStreaming: false,
          isOptimistic: false
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
    
    // Only apply pending placeholder if this chat doesn't already have a streaming OR loading message
    // and is currently active
    const hasActiveMessage = cleaned.some(m => m.isStreaming || m.isLoading)
    const pendingMeta = pendingStreamMetaRef.current[chatKey]
    
    if (!pendingMeta || hasActiveMessage || activeChatRef.current !== chatKey) {
      if (pendingMeta && (hasActiveMessage || activeChatRef.current !== chatKey)) {
        console.log('[applyPendingPlaceholder] ⚠️ Skipping placeholder - already has active message or not current chat')
      }
      return cleaned
    }
    
    console.log('[applyPendingPlaceholder] ⚠️ Adding loading placeholder for chat:', chatKey)
    
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
    // DO NOT update pendingStreamMetaRef here - it should only be set by sendMessage
    // and cleaned up when stream starts/completes
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

  const sendSubscribeRequest = useCallback((targetChatId) => {
    if (!targetChatId || isSharedView) return
    // Deduplicate rapid repeat subscribes for the same chat
    if (lastSubscribeChatIdRef.current === targetChatId && wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }
    lastSubscribeChatIdRef.current = targetChatId

    const payload = { type: 'subscribe', chat_id: targetChatId }
    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      // Queue it; it will be flushed on socket open
      pendingOutgoingMessagesRef.current.push(payload)
      return
    }
    try {
      socket.send(JSON.stringify(payload))
      if (isDev) {
        console.log('[WS] Sent subscribe request for chat:', targetChatId)
      }
    } catch (err) {
      console.error('[WS] Failed to send subscribe request:', err)
      pendingOutgoingMessagesRef.current.push(payload)
    }
  }, [isSharedView])

  const handleSocketMessage = useCallback((data) => {
    const targetChatId = data.chat_id
    const currentChatId = activeChatRef.current
    const resolvedChatId = targetChatId || currentChatId
    const isCurrentChat = !targetChatId || targetChatId === currentChatId

    if (!isCurrentChat) {
      console.log(`[WS] Message for other chat ${targetChatId}, type: ${data.type}`)
      if ((data.type === 'message' && data.role === 'assistant') || data.type === 'message_complete' || data.type === 'error') {
        console.log(`[WS] Notifying parent that chat ${targetChatId} stopped running`)
        resolvePendingStream(targetChatId)
        // CRITICAL: Always notify parent directly, don't rely on pendingMeta
        onChatPendingStateChange?.(targetChatId, false)
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
    } else if (data.type === 'subscription_confirmed') {
      // Handle subscription confirmation for an existing stream
      const streamId = data.stream_id
      const streamChatId = data.chat_id
      if (streamId) {
        console.log('[WS subscription_confirmed] ✅ Stream:', streamId, 'chat:', streamChatId, 'Current messages:', messages.length)
        // Set up stream tracking immediately
        streamingMessageIdRef.current = streamId
        activeStreamIdRef.current = streamId
        setIsStreaming(true)
        notifyStreamingStatus(true)  // Notify parent: chat is running
        streamIdToMessageIdRef.current[streamId] = streamId
        
        // CRITICAL: Clean up pendingStreamMeta since stream is already running
        if (streamChatId) {
          delete pendingStreamMetaRef.current[streamChatId]
          console.log('[WS subscription_confirmed] Cleaned up pendingStreamMeta for chat:', streamChatId)
        }
        // Initialize buffer if not exists
        if (!streamBuffersRef.current[streamId]) {
          streamBuffersRef.current[streamId] = { chunks: [], text: '' }
        }
        
        // Ensure a message exists to receive chunks
        setMessages(prev => {
          // Check if we already have a message for this stream
          const existingMsg = prev.find(m => m.id === streamId)
          if (existingMsg) {
            console.log('[WS subscription_confirmed] ✅ Message exists, marking as streaming. Content length:', existingMsg.content?.length || 0)
            // Just mark it as streaming
            return prev.map(m => m.id === streamId ? {
              ...m,
              isLoading: false,
              isStreaming: true,
              chatId: streamChatId || m.chatId || currentChatId
            } : m)
          }
          
          // Create a new message to receive the stream
          console.log('[WS subscription_confirmed] ⚠️ Creating NEW empty message for stream (this should receive accumulated content soon)')
          return [
            ...prev,
            {
              id: streamId,
              clientId: streamId,
              role: 'assistant',
              content: '',
              created_at: new Date().toISOString(),
              isLoading: false,
              isStreaming: true,
              isOptimistic: false,
              chatId: streamChatId || currentChatId
            }
          ]
        })
      }
    } else if (data.type === 'message_start') {
      const streamId = data.stream_id || `stream-${Date.now()}`
      const streamChatId = data.chat_id || currentChatId
      streamingMessageIdRef.current = streamId
      activeStreamIdRef.current = streamId
      setIsStreaming(true)
      notifyStreamingStatus(true)  // Notify parent: chat is running
      streamBuffersRef.current[streamId] = { chunks: [], text: '' }
      
      // CRITICAL: Clean up pendingStreamMeta since stream is now starting
      if (streamChatId) {
        delete pendingStreamMetaRef.current[streamChatId]
      }
      
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
            isStreaming: true,  // Start streaming
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
            isStreaming: true,  // Start streaming
            isOptimistic: true,
            chatId: currentChatId ?? null
          }
        ]
      })
    } else if (data.type === 'meta_info_update') {
      // Handle meta info update
      const infoContent = data.content || ''
      if (infoContent) {
        setMetaInfo(prev => prev + infoContent)
        if (isDev) {
          console.log('[WS meta_info]', infoContent.slice(0, 100))
        }
      }
    } else if (data.type === 'message_chunk') {
      const chunkText = extractChunkText(data.content)
      const streamId = data.stream_id || streamingMessageIdRef.current
      const chunkChatId = data.chat_id || currentChatId
      if (!chunkText || !streamId) {
        console.warn('[WS chunk] ⚠️ Missing chunkText or streamId!', {chunkText: !!chunkText, streamId})
        return
      }
      console.log('[WS chunk] 📦 Received', chunkText.length, 'chars for stream:', streamId, '(first 80 chars:', chunkText.substring(0, 80), '...)')
      
      // Ensure stream tracking is set up (in case message_start was missed)
      if (!streamingMessageIdRef.current) {
        streamingMessageIdRef.current = streamId
      }
      if (!activeStreamIdRef.current) {
        activeStreamIdRef.current = streamId
        setIsStreaming(true)
      }
      
      const chunkIndex = typeof data.chunk_index === 'number' ? data.chunk_index : null
      // Use existing mapping or use streamId as the message ID
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

      // Extract canvas content BEFORE storing in state to prevent flashing
      const { content: contentWithoutCanvas, canvasContent } = extractCanvasContent(mergedText)
      
      // Store the full content (with canvas) for canvas display to extract
      // But use contentWithoutCanvas for display to avoid flashing
      const contentToStore = mergedText  // Keep original for canvas extraction
      const rawContent = contentWithoutCanvas || mergedText  // For display without canvas

      setMessages(prev => {
        let found = false
        const updated = prev.map(msg => {
          if (msg.id === targetId) {
            found = true
            if (isDev) {
              console.log('[WS chunk] Updating message:', msg.id, 'old length:', msg.content?.length || 0, 'new length:', contentToStore.length)
            }
            return {
              ...msg,
              role: 'assistant',
              isLoading: false,
              isStreaming: true,  // Mark as actively streaming
              content: contentToStore,  // Full content with canvas for extraction
              _displayContent: rawContent,  // Content without canvas for immediate display
              isOptimistic: false,
              chatId: msg.chatId ?? chunkChatId ?? currentChatId ?? null
            }
          }
          return msg
        })

        if (!found) {
          console.log('[WS chunk] 🆕 Creating NEW message for stream:', streamId, 'with', contentToStore.length, 'chars. ChatId:', chunkChatId ?? currentChatId)
          return [
            ...prev,
            {
              id: targetId,
              clientId: targetId,
              role: 'assistant',
              isLoading: false,
              isStreaming: true,  // Mark as actively streaming
              content: contentToStore,  // Full content with canvas
              _displayContent: rawContent,  // Content without canvas
              created_at: new Date().toISOString(),
              isOptimistic: false,
              chatId: chunkChatId ?? currentChatId ?? null
            }
          ]
        }

        return updated
      })
      // Don't resolve pending stream yet - keep loading indicator during streaming
      // resolvePendingStream(currentChatId)
    } else if (data.type === 'message_complete') {
      const finalText = extractChunkText(data.content)
      const streamId = data.stream_id || streamingMessageIdRef.current
      const targetId = streamId ? (streamIdToMessageIdRef.current[streamId] || streamId) : null
      console.log('[WS message_complete] ✅ Stream completed!', {
        streamId, 
        targetId, 
        finalLength: finalText?.length || 0,
        currentMessages: messages.length
      })
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
          // Still clear all flags even if message exists
          return prev.map(m => {
            if (m.role === 'assistant' && (!m.chatId || m.chatId === resolvedChatId || m.chatId === currentChatId)) {
              return { ...m, isLoading: false, isStreaming: false, isOptimistic: false }
            }
            return m
          })
        }
        const updated = prev.map(msg => {
          if (msg.id === targetId) {
            updatedFlag = true
            if (isDev) {
              console.log('[WS message_complete] Updating message ID from', targetId, 'to', data.id)
            }
            const updated = {
              ...msg,
              id: data.id,
              clientId: msg.clientId || `server-${data.id}`,
              role: data.role,
              isLoading: false,
              isStreaming: false,
              created_at: data.created_at,
              content: finalText || msg.content || '',
              _displayContent: undefined,  // Clear temp display content
              isOptimistic: false,
              chatId: resolvedChatId ?? msg.chatId ?? currentChatId ?? null
            }
            console.log('[WS message_complete] ✅ Updated message flags:', {
              id: updated.id,
              isLoading: updated.isLoading,
              isStreaming: updated.isStreaming,
              contentLength: updated.content?.length
            })
            return updated
          }
          // CRITICAL: Clear flags on ALL assistant messages in this chat
          if (msg.role === 'assistant' && (!msg.chatId || msg.chatId === resolvedChatId || msg.chatId === currentChatId)) {
            return { ...msg, isLoading: false, isStreaming: false, isOptimistic: false }
          }
          return msg
        })
        if (!updatedFlag) {
          if (isDev) {
            console.log('[WS message_complete] Message not found, appending new one for stream:', streamId)
          }
          // Clear flags on existing messages and append new one
          const cleaned = prev.map(m => {
            if (m.role === 'assistant' && (!m.chatId || m.chatId === resolvedChatId || m.chatId === currentChatId)) {
              return { ...m, isLoading: false, isStreaming: false, isOptimistic: false }
            }
            return m
          })
          return [
            ...cleaned,
            {
              id: data.id,
              clientId: `server-${data.id}`,
              role: data.role,
              content: finalText,
              created_at: data.created_at,
              chatId: resolvedChatId ?? currentChatId ?? null,
              isLoading: false,
              isStreaming: false,
              isOptimistic: false
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
      activeStreamIdRef.current = null
      setIsStreaming(false)
      notifyStreamingStatus(false)  // Notify parent: chat is complete
      resolvePendingStream(resolvedChatId ?? currentChatId)
      
      // Flags are already cleared in the setMessages above (lines 636-637)
      // Don't need a second setMessages call
      
      onChatUpdateRef.current?.()
      // Short delay to ensure message is saved to DB before fetching
      setTimeout(() => {
        fetchMessagesRef.current({ showLoader: false })
      }, 200)
    } else if (data.type === 'no_active_stream') {
      // No active stream for this chat - make sure we're not showing loading state
      console.log('[WS no_active_stream] No active stream for chat, clearing any loading state')
      setIsStreaming(false)
      notifyStreamingStatus(false)
      resolvePendingStream(currentChatId)
      // Clear any loading flags on messages
      setMessages(prev => prev.map(m => {
        if (m.role === 'assistant' && (!m.chatId || m.chatId === currentChatId)) {
          return { ...m, isLoading: false, isStreaming: false, isOptimistic: false }
        }
        return m
      }))
    } else if (data.type === 'error') {
      console.error('Server error:', data.message)
      setConnectionNotice(data.message || 'An error occurred')
      const streamId = data.stream_id
      // Keep the partial response, just mark it as no longer loading
      if (streamId && streamIdToMessageIdRef.current[streamId]) {
        const targetId = streamIdToMessageIdRef.current[streamId]
        setMessages(prev => prev.map(m => {
          if (m.id === targetId) {
            // Keep content, just stop loading
            return { ...m, isLoading: false, isOptimistic: false }
          }
          return m
        }))
        delete streamIdToMessageIdRef.current[streamId]
      } else {
        // Mark all loading messages as done (keep their content)
        setMessages(prev => prev.map(m => m.isLoading ? { ...m, isLoading: false } : m))
      }
      streamingMessageIdRef.current = null
      activeStreamIdRef.current = null
      setIsStreaming(false)
      notifyStreamingStatus(false)  // Notify parent: chat stopped (error)
      
      // Only clear loading/streaming flags for assistant messages in this chat
      setMessages(prev => prev.map(m => {
        if (m.role === 'assistant' && (m.chatId === currentChatId || !m.chatId)) {
          return { ...m, isLoading: false, isStreaming: false }
        }
        return m
      }))
      
      resolvePendingStream(currentChatId)
      pendingWaitingMessageIdsRef.current = []
    }
  }, [resolvePendingStream, notifyStreamingStatus])

  useEffect(() => {
    activeChatRef.current = chatId ?? null
    setConnectionNotice('')
    streamIdToMessageIdRef.current = {}
    streamBuffersRef.current = {}
    pendingWaitingMessageIdsRef.current = []
    streamingMessageIdRef.current = null
    activeStreamIdRef.current = null
    setIsStreaming(false)  // Reset streaming state for new chat
    // CRITICAL: Notify parent (sidebar) that this chat is not streaming
    if (chatId) {
      notifyStreamingStatus(false)
    }
    // Don't clear messages here - let fetchMessages replace them
    // This prevents flash of empty content during fetch
    // setMessages([])

    // For shared chats, we don't need userId
    if (!chatId || (!userId && !isSharedView)) {
      fetchMessagesRef.current = async () => {}
      return
    }

    let isCurrent = true
    const requestId = ++requestIdRef.current

    const fetchMessages = async ({ showLoader = true } = {}) => {
      // For shared chats with data already provided, skip loading state
      if (isSharedView && sharedChatData) {
        // Use shared chat data directly
        const uniqueMessages = sharedChatData.messages.reduce((acc, msg) => {
          if (!acc.some(m => m.id === msg.id)) {
            acc.push(msg)
          }
          return acc
        }, [])
        uniqueMessages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        setMessages((prev) => {
          const normalized = normalizeMessages(uniqueMessages.map((msg) => ({ ...msg, chatId })), chatId)
          return normalized
        })
        if (sharedChatData.meta_info !== undefined) {
          setMetaInfo(sharedChatData.meta_info || '')
        }
        setLoading(false)
        return
      }

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

        // Update meta_info
        if (response.data.meta_info !== undefined) {
          setMetaInfo(response.data.meta_info || '')
        }
        
        const uniqueMessages = response.data.messages.reduce((acc, msg) => {
          if (!acc.some(m => m.id === msg.id)) {
            acc.push(msg)
          }
          return acc
        }, [])
        uniqueMessages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        setMessages((prev) => {
          // If switching chats, only use messages for this chat
          const prevForThisChat = prev.filter(m => m.chatId === chatId || !m.chatId)
          
          const normalized = normalizeMessages(uniqueMessages.map((msg) => ({ ...msg, chatId })), chatId)
          
          // CRITICAL: If we have more content locally than from the server, preserve local content
          // This prevents losing content during the window between stream completion and DB save
          const prevAssistantWithContent = prevForThisChat.filter(m => 
            m.role === 'assistant' && m.content && m.content.trim().length > 0
          )
          const normalizedAssistantWithContent = normalized.filter(m => 
            m.role === 'assistant' && m.content && m.content.trim().length > 0
          )
          
          // If we had content locally but server returned less, keep local messages
          if (prevAssistantWithContent.length > normalizedAssistantWithContent.length) {
            console.log('[fetchMessages] ⚠️ Preserving local content - server has fewer messages than local state')
            // Just clear loading flags on existing messages
            return prev.filter(m => m.chatId === chatId || !m.chatId).map(m => ({
              ...m,
              isLoading: false,
              isStreaming: false,
              isOptimistic: false
            }))
          }
          
          // Clear any loading/streaming flags since we're getting fresh data from server
          const cleanedNormalized = normalized.map(m => ({
            ...m,
            isLoading: false,
            isStreaming: false,
            isOptimistic: false
          }))
          
          return cleanedNormalized
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
    
    // Subscribe to any active stream for this chat when chat changes
    sendSubscribeRequest(chatId)

    return () => {
      isCurrent = false
    }
  }, [chatId, userId, isSharedView, sharedChatData, sendSubscribeRequest])

  useEffect(() => {
    // For shared chats, we don't need WebSocket connection
    if (isSharedView) {
      if (wsRef.current) {
        try {
          wsRef.current.close()
        } catch (err) {
          console.error('Error closing socket:', err)
        }
        wsRef.current = null
      }
      setConnected(true) // Mark as "connected" for shared chats (read-only mode)
      return
    }

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
      // Check for direct backend WebSocket URL from environment variable
      const backendWsUrl = import.meta.env.VITE_BACKEND_WS_URL
      let wsUrl
      if (backendWsUrl) {
        // Use direct backend connection (bypasses Vite proxy)
        wsUrl = `${backendWsUrl}/ws/${userId}`
      } else {
        // Use relative path for WebSocket to go through Vite proxy
        // The proxy will forward /ws to the backend WebSocket server
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsHost = window.location.host
        wsUrl = `${wsProtocol}//${wsHost}/ws/${userId}`
      }
      const socket = new WebSocket(wsUrl)
      wsRef.current = socket
      console.log('Opening WebSocket:', wsUrl)

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
        
        // Always subscribe to the *current* chat (avoid stale chatId closure)
        sendSubscribeRequest(activeChatRef.current)
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
  }, [userId, flushPendingMessages, handleSocketMessage, sendSubscribeRequest])

  useEffect(() => {
    if (!chatId || !userId) return
    const interval = setInterval(() => {
      // Don't poll if actively streaming in this chat
      const hasActiveStream = Object.keys(streamBuffersRef.current).length > 0
      if (!hasActiveStream) {
        fetchMessagesRef.current({ showLoader: false })
      }
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

    // Prevent duplicate sends - check if THIS chat already has a pending response
    const hasPendingResponse = messages.some(m => 
      (m.isLoading || m.isStreaming) && m.role === 'assistant'
    )
    if (hasPendingResponse) {
      const pendingMsg = messages.find(m => (m.isLoading || m.isStreaming) && m.role === 'assistant')
      console.warn('Message already being sent in this chat, ignoring duplicate send. Pending message:', {
        id: pendingMsg?.id,
        isLoading: pendingMsg?.isLoading,
        isStreaming: pendingMsg?.isStreaming,
        contentLength: pendingMsg?.content?.length
      })
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

    // Set streaming state IMMEDIATELY to prevent duplicate sends
    setIsStreaming(true)  // Show stop button immediately and prevent duplicate sends
    notifyStreamingStatus(true)  // Notify parent: chat is now running
    
    const waitingId = generateClientId()
    streamingMessageIdRef.current = waitingId
    activeStreamIdRef.current = waitingId  // Set immediately so stop button shows
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

    // Get tool preferences from localStorage (frontend-managed).
    // Default: web_search enabled.
    let enabled_tools = { web_search: true }
    if (userId && typeof window !== 'undefined') {
      const stored = localStorage.getItem(`tools_${userId}`)
      if (stored) {
        try {
          const parsed = JSON.parse(stored)
          if (parsed && typeof parsed === 'object') {
            enabled_tools = { ...enabled_tools, ...parsed }
          }
        } catch (e) {
          console.error('Failed to parse tool preferences:', e)
        }
      }
    }

    const payload = {
      type: 'message',
      chat_id: chatId,
      content: trimmed,
      model: selectedModel,
      meta_info: metaInfo,
      enabled_tools: enabled_tools  // Pass tool preferences
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
      // Keep isStreaming true since message will be sent when connection is ready
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
      setIsStreaming(false)  // Reset streaming state on error
      notifyStreamingStatus(false)  // Notify parent: chat stopped (send error)
      activeStreamIdRef.current = null
    }
  }

  const handleShare = useCallback(async () => {
    if (!chatId || !userId) return
    
    try {
      const response = await axios.post(`/api/chats/${chatId}/share`, null, {
        params: { user_id: userId }
      })
      
      const url = response.data.share_url
      setShareUrl(url)
      
      // Copy to clipboard with fallback for HTTP
      try {
        // Try modern Clipboard API (requires HTTPS)
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(url)
        } else {
          // Fallback for HTTP: use execCommand
          const textArea = document.createElement('textarea')
          textArea.value = url
          textArea.style.position = 'fixed'
          textArea.style.left = '-999999px'
          textArea.style.top = '-999999px'
          document.body.appendChild(textArea)
          textArea.focus()
          textArea.select()
          try {
            document.execCommand('copy')
            textArea.remove()
          } catch (err) {
            textArea.remove()
            // If both methods fail, show prompt
            prompt('Copy this share link:', url)
            return
          }
        }
        setShareCopied(true)
        setShowShareNotification(true)
        
        // Reset copied state after 2 seconds
        setTimeout(() => {
          setShareCopied(false)
        }, 2000)
        
        // Hide notification after 3 seconds
        setTimeout(() => {
          setShowShareNotification(false)
        }, 3000)
      } catch (clipboardError) {
        // If clipboard fails, show prompt as last resort
        prompt('Copy this share link:', url)
      }
    } catch (error) {
      console.error('Error sharing chat:', error)
      setConnectionNotice('Failed to generate share link')
    }
  }, [chatId, userId])

  // Survey handlers
  const checkAndShowSurvey = useCallback(async (targetChatId) => {
    const surveyMode = import.meta.env.VITE_SURVEY_MODE || 'optional'
    if (surveyMode === 'disabled' || !targetChatId || !userId) return

    try {
      const response = await axios.get(`/api/surveys/${targetChatId}`, {
        params: { user_id: userId }
      })

      if (!response.data.exists) {
        // Get chat meta_info for context
        try {
          const chatResponse = await axios.get(`/api/chats/${targetChatId}`, {
            params: { user_id: userId }
          })
          setChatMetaInfo(chatResponse.data.meta_info || '')
        } catch (err) {
          console.error('Failed to fetch chat meta_info:', err)
          setChatMetaInfo('')
        }
        setSurveyForChatId(targetChatId)
        setShowSurvey(true)
      }
    } catch (err) {
      console.error('Failed to check survey:', err)
    }
  }, [userId])

  const handleSurveySubmit = useCallback(async (responses) => {
    if (!surveyForChatId || !userId) return

    try {
      await axios.post('/api/surveys', {
        chat_id: surveyForChatId,
        ...responses
      }, {
        params: { user_id: userId }
      })

      setShowSurvey(false)
      setSurveyForChatId(null)
    } catch (err) {
      console.error('Failed to submit survey:', err)
      alert('Failed to submit survey. Please try again.')
    }
  }, [surveyForChatId, userId])

  const handleSurveySkip = useCallback(() => {
    const surveyMode = import.meta.env.VITE_SURVEY_MODE || 'optional'
    if (surveyMode !== 'mandatory') {
      setShowSurvey(false)
      setSurveyForChatId(null)
    }
  }, [])

  // Set up survey request callback
  useEffect(() => {
    if (onSurveyRequested) {
      onSurveyRequested(() => checkAndShowSurvey)
    }
  }, [onSurveyRequested, checkAndShowSurvey])

  const handleMouseDown = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleMouseMove = useCallback((e) => {
    if (!isDragging) return
    
    const container = document.querySelector('.chat-window')
    if (!container) return
    
    const containerRect = container.getBoundingClientRect()
    const newRatio = ((e.clientX - containerRect.left) / containerRect.width) * 100
    
    // Constrain between 20% and 80%
    if (newRatio >= 20 && newRatio <= 80) {
      setSplitRatio(newRatio)
    }
  }, [isDragging])

  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
  }, [])

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  const stopGeneration = useCallback(() => {
    const socket = wsRef.current
    const streamId = activeStreamIdRef.current
    
    if (isDev) {
      console.log('[stopGeneration] Called', { 
        hasSocket: !!socket, 
        socketReady: socket?.readyState === WebSocket.OPEN,
        streamId, 
        isStreaming, 
        chatId
      })
    }
    
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      console.warn('Cannot stop generation: WebSocket not connected')
      return
    }
    
    if (!streamId && !isStreaming) {
      console.warn('No active stream to stop')
      return
    }
    
    try {
      const payload = {
        type: 'stop',
        chat_id: chatId,
        stream_id: streamId
      }
      if (isDev) {
        console.log('[WS send stop]', payload)
      }
      socket.send(JSON.stringify(payload))
    } catch (err) {
      console.error('Failed to send stop message:', err)
    }
  }, [chatId, isStreaming])

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

  const models = ['Auto', 'GPT-5 mini', 'GPT-5 nano', 'GPT-5.2', 'GPT-5 mini (Search)', 'GPT-5.2 (Search)']

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

  // Show login UI only if not viewing a shared chat
  if (!user && !isSharedView) {
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
          <div className="header-right">
            <button 
              className={`canvas-toggle-button ${canvasOpen ? 'active' : ''}`}
              onClick={() => setCanvasOpen(!canvasOpen)}
              title={canvasOpen ? 'Hide canvas' : 'Show canvas'}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <line x1="15" y1="3" x2="15" y2="21"></line>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="3" y1="15" x2="21" y2="15"></line>
              </svg>
            </button>
            <div className="chat-status">
              <span className="status-indicator disconnected">● Please log in</span>
            </div>
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
          <div className="header-right">
            <button 
              className={`canvas-toggle-button ${canvasOpen ? 'active' : ''}`}
              onClick={() => setCanvasOpen(!canvasOpen)}
              title={canvasOpen ? 'Hide canvas' : 'Show canvas'}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <line x1="15" y1="3" x2="15" y2="21"></line>
                <line x1="3" y1="9" x2="21" y2="9"></line>
                <line x1="3" y1="15" x2="21" y2="15"></line>
              </svg>
            </button>
            <div className="chat-status"></div>
          </div>
        </div>
        <div className="chat-body">
          <MessageList messages={[]} />
        </div>
        <div className={`message-input-wrapper ${canvasOpen ? 'with-canvas' : ''}`}>
          <MessageInput onSendMessage={sendMessage} disabled isStreaming={false} />
        </div>
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
        <div className="header-right">
          {chatId && userId && !isSharedView && (
            <button 
              className={`share-button ${shareCopied ? 'copied' : ''}`}
              onClick={handleShare}
              title={shareCopied ? 'Link copied!' : 'Share chat'}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </button>
          )}
          <button 
            className={`canvas-toggle-button ${canvasOpen ? 'active' : ''}`}
            onClick={() => setCanvasOpen(!canvasOpen)}
            title={canvasOpen ? 'Hide canvas' : 'Show canvas'}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
              <line x1="9" y1="3" x2="9" y2="21"></line>
              <line x1="15" y1="3" x2="15" y2="21"></line>
              <line x1="3" y1="9" x2="21" y2="9"></line>
              <line x1="3" y1="15" x2="21" y2="15"></line>
            </svg>
          </button>
          <div className="chat-status">
            {isSharedView ? (
              <span className="status-indicator shared">● Shared Chat</span>
            ) : connected ? (
              <span className="status-indicator connected">● Connected</span>
            ) : (
              <span className="status-indicator disconnected">● Connecting...</span>
            )}
          </div>
        </div>
      </div>
      <div className={`chat-body ${canvasOpen ? 'with-canvas' : ''} ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="chat-content" style={canvasOpen ? { width: `${splitRatio}%` } : {}}>
          {connectionNotice && (
            <div className="connection-notice">
              {connectionNotice}
            </div>
          )}
          {showShareNotification && (
            <div className="share-notification">
              ✓ Link copied!
            </div>
          )}
          {loading ? (
            <div className="loading-messages">Loading messages...</div>
          ) : (
            <MessageList messages={messages} />
          )}
        </div>
        {canvasOpen && (
          <>
            <div className="canvas-overlay" onClick={() => setCanvasOpen(false)} />
            <div 
              className="resize-handle"
              onMouseDown={handleMouseDown}
            >
              <div className="resize-handle-line" />
            </div>
            <div className="canvas-panel" style={{ width: `${100 - splitRatio}%` }}>
              <div className="canvas-container">
                <CanvasDisplay messages={messages} />
              </div>
            </div>
          </>
        )}
      </div>
      <div className={`message-input-wrapper ${canvasOpen ? 'with-canvas' : ''}`} style={canvasOpen ? { width: `${splitRatio}%` } : {}}>
        <MessageInput
          onSendMessage={sendMessage}
          onStopGeneration={stopGeneration}
          disabled={!chatId || isSharedView}
          isStreaming={isStreaming}
        />
      </div>

      {/* Survey Modal */}
      {showSurvey && surveyForChatId && (
        <SurveyModal
          chatId={surveyForChatId}
          userPreferences={chatMetaInfo}
          onSubmit={handleSurveySubmit}
          onSkip={handleSurveySkip}
          isMandatory={import.meta.env.VITE_SURVEY_MODE === 'mandatory'}
          onClose={handleSurveySkip}
        />
      )}
    </div>
  )
}

export default ChatWindow
