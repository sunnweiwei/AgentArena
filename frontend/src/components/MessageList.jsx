import React, { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { AgentContent, extractCanvasContent, DiffBlock } from './AgentBlock'
import './MessageList.css'

const MessageList = ({ messages, onScrollToBottom }) => {
  const listRef = useRef(null)
  const prevSignatureRef = useRef({ id: null, length: 0 })
  const isFirstRenderRef = useRef(true)

  const scrollToBottom = (behavior = 'smooth') => {
    const listEl = listRef.current
    if (!listEl) return
    const scrollBehavior = behavior
    requestAnimationFrame(() => {
      listEl.scrollTo({
        top: listEl.scrollHeight,
        behavior: scrollBehavior
      })
    })
    if (typeof onScrollToBottom === 'function') {
      onScrollToBottom()
    }
  }

  useEffect(() => {
    if (!messages || messages.length === 0) {
      prevSignatureRef.current = { id: null, length: 0 }
      isFirstRenderRef.current = true
      return
    }

    const lastMessage = messages[messages.length - 1]
    const signature = {
      id: lastMessage?.clientId || lastMessage?.id || `idx-${messages.length - 1}`,
      length: (lastMessage?.content || '').length,
      isLoading: Boolean(lastMessage?.isLoading)
    }
    const prevSignature = prevSignatureRef.current
    const hasNewMessage = signature.id !== prevSignature.id
    const contentExtended = signature.id === prevSignature.id && signature.length > (prevSignature.length || 0)
    const shouldScroll =
      isFirstRenderRef.current ||
      hasNewMessage ||
      contentExtended ||
      signature.isLoading

    if (shouldScroll) {
      const useSmoothScroll = !isFirstRenderRef.current && messages.length > 2
      scrollToBottom(useSmoothScroll ? 'smooth' : 'auto')
    }

    prevSignatureRef.current = signature
    isFirstRenderRef.current = false
  }, [messages])

  return (
    <div className="message-list" ref={listRef}>
      {messages.length === 0 ? (
        <div className="empty-messages">
          <p>No messages yet. Start the conversation!</p>
        </div>
      ) : (
        <>
          {messages.map((message, index) => {
            // Check if message contains agent markup (think/tool tags) - only for assistant messages
            const hasAgentMarkup = message.role === 'assistant' && message.content && 
              (message.content.includes('<|think|>') || message.content.includes('<|tool|>'))
            
            // For assistant messages, use pre-processed display content if available (avoids flashing)
            // Otherwise extract canvas content on the fly (for older messages from DB)
            const displayContent = message.role === 'assistant' 
              ? (message._displayContent || (message.content ? extractCanvasContent(message.content).content : ''))
              : message.content
            
            // Determine loading state: show skeleton only if no content yet
            // Check _displayContent first (for streaming messages), fall back to content
            const contentToCheck = message._displayContent || message.content
            const hasContent = contentToCheck && contentToCheck.trim().length > 0
            // Priority: if has content, never show skeleton, only inline loading
            const showSkeleton = !hasContent && (message.isLoading || message.isStreaming)
            const showInlineLoading = hasContent && (message.isLoading || message.isStreaming)
            
            return (
            <div key={message.clientId || message.id || index} className={`message ${message.role}`}>
              <div className="message-content">
                {showSkeleton ? (
                  <div className="typing-indicator">
                      <div className="skeleton-line"></div>
                      <div className="skeleton-line"></div>
                      <div className="skeleton-line"></div>
                    </div>
                  ) : hasAgentMarkup ? (
                    <AgentContent content={message.content} showInlineLoading={showInlineLoading} />
                  ) : (
                    <>
                      {message.role === 'user' ? (
                        <div className="user-bubble">
                          <ReactMarkdown 
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw]}
                            components={{
                              img: ({node, ...props}) => (
                                <img 
                                  {...props} 
                                  style={{maxWidth: '100%', height: 'auto', borderRadius: '8px', marginTop: '8px', marginBottom: '8px'}}
                                  loading="lazy"
                                />
                              ),
                              code: ({node, inline, className, children, ...props}) => {
                                const match = /language-(\w+)/.exec(className || '')
                                const language = match ? match[1] : ''
                                const content = String(children).replace(/\n$/, '')
                                
                                if (!inline && (language === 'diff' || language === 'patch')) {
                                  return <DiffBlock content={content} />
                                }
                                
                                return inline ? (
                                  <code className={className} {...props}>{children}</code>
                                ) : (
                                  <code className={className} {...props}>{children}</code>
                                )
                              }
                            }}
                          >
                            {displayContent}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <ReactMarkdown 
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeRaw]}
                          components={{
                            img: ({node, ...props}) => (
                              <img 
                                {...props} 
                                style={{maxWidth: '100%', height: 'auto', borderRadius: '8px', marginTop: '8px', marginBottom: '8px'}}
                                loading="lazy"
                              />
                            ),
                            code: ({node, inline, className, children, ...props}) => {
                              const match = /language-(\w+)/.exec(className || '')
                              const language = match ? match[1] : ''
                              const content = String(children).replace(/\n$/, '')
                              
                              if (!inline && (language === 'diff' || language === 'patch')) {
                                return <DiffBlock content={content} />
                              }
                              
                              return inline ? (
                                <code className={className} {...props}>{children}</code>
                              ) : (
                                <code className={className} {...props}>{children}</code>
                              )
                            }
                          }}
                        >
                          {displayContent}
                        </ReactMarkdown>
                      )}
                      {showInlineLoading && (
                        <span className="inline-loading">
                    <span></span>
                    <span></span>
                    <span></span>
                        </span>
                      )}
                    </>
                )}
              </div>
            </div>
            )
          })}
        </>
      )}
    </div>
  )
}

export default MessageList

