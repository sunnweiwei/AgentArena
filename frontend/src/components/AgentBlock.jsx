import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import './AgentBlock.css'

/**
 * Extract canvas content from message and return content without canvas parts
 * Returns { content: string (without canvas), canvasContent: string | null (last canvas) }
 */
export function extractCanvasContent(content) {
  if (!content) return { content: '', canvasContent: null }
  
  const canvasRegex = /<\|canvas\|>([\s\S]*?)<\|\/canvas\|>/g
  let lastCanvasContent = null
  let match
  
  // Find the last canvas content
  while ((match = canvasRegex.exec(content)) !== null) {
    lastCanvasContent = match[1].trim()
  }
  
  // Remove all canvas blocks from content
  const contentWithoutCanvas = content.replace(canvasRegex, '').trim()
  
  return {
    content: contentWithoutCanvas,
    canvasContent: lastCanvasContent
  }
}

/**
 * Get the last canvas content from all messages
 */
export function getLastCanvasContent(messages) {
  if (!messages || messages.length === 0) return null
  
  // Search from the end for efficiency
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.role === 'assistant' && msg.content) {
      const { canvasContent } = extractCanvasContent(msg.content)
      if (canvasContent) {
        return canvasContent
      }
    }
  }
  return null
}

/**
 * Parse function calls from text (used only for content outside of tool blocks)
 */
function parseFunctionCalls(text) {
  const parts = []
  let position = 0
  
  const functionRegex = /<function=([^>]+)>\s*(.*?)\s*<\/function>/gs
  const matches = [...text.matchAll(functionRegex)]
  
  for (const match of matches) {
    const startIndex = match.index
    const endIndex = startIndex + match[0].length
    
    // Add text before this match
    if (startIndex > position) {
      const textBefore = text.substring(position, startIndex)
      if (textBefore.trim()) {
        parts.push({ type: 'text', content: textBefore })
      }
    }
    
    const functionName = match[1]
    const paramsXml = match[2]
    
    // Extract parameters
    const paramRegex = /<parameter=([^>]+)>(.*?)<\/parameter>|<parameter>(.*?)<\/parameter>/gs
    const params = {}
    let paramMatch
    while ((paramMatch = paramRegex.exec(paramsXml)) !== null) {
      if (paramMatch[1]) {
        params[paramMatch[1]] = paramMatch[2].trim()
      } else if (paramMatch[3]) {
        if (!params._unnamed) params._unnamed = []
        params._unnamed.push(paramMatch[3].trim())
      }
    }
    
    parts.push({
      type: 'tool-call',
      functionName: functionName,
      params: params,
      isStandalone: true
    })
    
    position = endIndex
  }
  
  // Add remaining text
  if (position < text.length) {
    const textAfter = text.substring(position)
    if (textAfter.trim()) {
      parts.push({ type: 'text', content: textAfter })
    }
  }
  
  return parts
}

/**
 * Parse agent markup from message content
 * Handles <|think|>, <|tool|> tags and extracts tool calls from XML format
 * Note: Function calls are NOT extracted from inside <|tool|> blocks
 * Note: Canvas content should be extracted separately using extractCanvasContent
 */
export function parseAgentMarkup(content) {
  if (!content) return [{ type: 'text', content: '' }]
  
  // First remove canvas content (it should be displayed in canvas box, not chat)
  const { content: contentWithoutCanvas } = extractCanvasContent(content)
  content = contentWithoutCanvas

  const parts = []
  let position = 0

  // First pass: find <|think|>, <|tool|>, and <|highlight|> blocks
  const blockRegex = /<\|(think|tool|highlight)\|>(.*?)<\|\/\1\|>/gs
  const matches = [...content.matchAll(blockRegex)]

  for (const match of matches) {
    const startIndex = match.index
    const endIndex = startIndex + match[0].length

    // Process text before this block (may contain function calls)
    if (startIndex > position) {
      const textBefore = content.substring(position, startIndex)
      if (textBefore.trim()) {
        // Parse function calls from text outside of tool blocks
        const textParts = parseFunctionCalls(textBefore)
        parts.push(...textParts)
      }
    }

    if (match[1] === 'think') {
      // Think block - keep as is
      parts.push({ type: 'think', content: match[2] })
    } else if (match[1] === 'tool') {
      // Tool results block - DO NOT parse function calls inside
      parts.push({ type: 'tool-results', content: match[2] })
    } else if (match[1] === 'highlight') {
      // Highlight block - keep as is, no function call parsing
      parts.push({ type: 'highlight', content: match[2] })
    }

    position = endIndex
  }

  // Process remaining text after last block (may contain function calls)
  if (position < content.length) {
    const textAfter = content.substring(position)
    if (textAfter.trim()) {
      const textParts = parseFunctionCalls(textAfter)
      parts.push(...textParts)
    }
  }

  // Group consecutive tool calls together
  const groupedParts = []
  let toolCallGroup = []
  
  for (const part of parts) {
    if (part.type === 'tool-call') {
      toolCallGroup.push(part)
    } else {
      if (toolCallGroup.length > 0) {
        // Add grouped tool calls with isFirst/isLast markers
        toolCallGroup.forEach((call, index) => {
          groupedParts.push({
            ...call,
            isFirst: index === 0,
            isLast: index === toolCallGroup.length - 1
          })
        })
        toolCallGroup = []
      }
      groupedParts.push(part)
    }
  }
  
  // Don't forget remaining tool calls
  if (toolCallGroup.length > 0) {
    toolCallGroup.forEach((call, index) => {
      groupedParts.push({
        ...call,
        isFirst: index === 0,
        isLast: index === toolCallGroup.length - 1
      })
    })
  }

  return groupedParts.length > 0 ? groupedParts : [{ type: 'text', content: content }]
}

/**
 * Get the primary argument to display for a tool call
 * Handles both named and unnamed parameters
 */

function getPrimaryArg(functionName, params) {
  if (functionName === 'search') {
    return params.query || params._unnamed?.[0] || ''
  } else if (functionName === 'extract') {
    return params.url || params._unnamed?.[0] || ''
  }
  // Default: show first named parameter or first unnamed parameter
  const namedParams = Object.keys(params).filter(k => k !== '_unnamed')
  if (namedParams.length > 0) {
    return params[namedParams[0]] || ''
  }
  return params._unnamed?.[0] || ''
}

/**
 * Think block component with collapsible content
 */
export function ThinkBlock({ content }) {
  const [isCollapsed, setIsCollapsed] = React.useState(true)  // Default: collapsed
  
  return (
    <div className="agent-block think">
      <div 
        className="think-header" 
        onClick={() => setIsCollapsed(!isCollapsed)}
        title={isCollapsed ? "Click to expand" : "Click to collapse"}
      >
        <span className={`think-arrow ${isCollapsed ? 'collapsed' : ''}`}>▼</span>
        <span>Thought</span>
      </div>
      <div className={`think-content-wrapper ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="think-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  )
}

/**
 * Tool call block component (one line, compact)
 */
export function ToolCallBlock({ functionName, params, isFirst, isLast, hasResults }) {
  const primaryArg = getPrimaryArg(functionName, params)
  
  return (
    <div 
      className={`agent-block tool-call ${isFirst ? 'first' : ''} ${isLast ? 'last' : ''} ${hasResults ? 'has-results' : ''}`}
      style={{
        borderTopLeftRadius: isFirst ? '6px' : '0',
        borderTopRightRadius: isFirst ? '6px' : '0',
        borderBottomLeftRadius: (isLast && !hasResults) ? '6px' : '0',
        borderBottomRightRadius: (isLast && !hasResults) ? '6px' : '0'
      }}
    >
      <div className="tool-call-content">
        <svg className="tool-call-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
        <span className="tool-call-name">{functionName}:</span>
        <span className="tool-call-args">{primaryArg}</span>
      </div>
    </div>
  )
}

/**
 * Tool results block component (scrollable, max 5 lines)
 */
export function ToolResultsBlock({ content, connectedToTool }) {
  return (
    <div className={`agent-block tool-results ${connectedToTool ? 'connected-to-tool' : ''}`}>
      <div className="tool-results-content">{content}</div>
    </div>
  )
}

/**
 * Highlight block component with green styling
 */
export function HighlightBlock({ content }) {
  return (
    <div className="agent-block highlight">
      <div className="highlight-content">
        <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

/**
 * Main component to render parsed agent content
 */
export function AgentContent({ content, showInlineLoading = false }) {
  const parts = parseAgentMarkup(content)
  
  return (
    <div className="agent-content">
      {parts.map((part, index) => {
        if (part.type === 'text') {
          const isLastPart = index === parts.length - 1
          return (
            <div key={index} className="agent-text">
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
                  )
                }}
              >
                {part.content}
              </ReactMarkdown>
              {showInlineLoading && isLastPart && (
                <span className="inline-loading">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              )}
            </div>
          )
        } else if (part.type === 'think') {
          return <ThinkBlock key={index} content={part.content} />
        } else if (part.type === 'highlight') {
          const isLastPart = index === parts.length - 1
          return (
            <React.Fragment key={index}>
              <HighlightBlock content={part.content} />
              {showInlineLoading && isLastPart && (
                <span className="inline-loading">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              )}
            </React.Fragment>
          )
        } else if (part.type === 'tool-call') {
          // Check if next part is tool-results
          const nextPart = parts[index + 1]
          const hasResults = nextPart && nextPart.type === 'tool-results'
          const isLastPart = index === parts.length - 1
          
          return (
            <React.Fragment key={index}>
              <ToolCallBlock
                functionName={part.functionName}
                params={part.params}
                isFirst={part.isFirst !== undefined ? part.isFirst : true}
                isLast={part.isLast !== undefined ? part.isLast : true}
                hasResults={hasResults && part.isLast}
              />
              {showInlineLoading && isLastPart && (
                <span className="inline-loading">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              )}
            </React.Fragment>
          )
        } else if (part.type === 'tool-results') {
          // Check if previous part is tool-call
          const prevPart = parts[index - 1]
          const connectedToTool = prevPart && prevPart.type === 'tool-call'
          const isLastPart = index === parts.length - 1
          
          return (
            <React.Fragment key={index}>
              <ToolResultsBlock
                content={part.content}
                connectedToTool={connectedToTool}
              />
              {showInlineLoading && isLastPart && (
                <span className="inline-loading">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              )}
            </React.Fragment>
          )
        }
        return null
      })}
    </div>
  )
}
