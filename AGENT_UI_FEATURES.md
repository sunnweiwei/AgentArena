# Agent UI Features - Think and Tool Call Visualization

## Overview

The frontend now supports beautiful visualization of agent thinking processes and tool calls. When the search agent (or any agent) returns responses with special markup, they are rendered as distinct visual blocks.

## Markup Format

### 1. Think Blocks
```
<|think|>
Agent's internal reasoning goes here...
This can be multiple lines.
<|/think|>
```

### 2. Tool Call Blocks (XML Format)
```
<function=search>
<parameter=query>What is the weather in Tokyo?</parameter>
<parameter=max_results>5</parameter>
</function>

<function=extract>
<parameter=url>https://example.com</parameter>
</function>
```

### 3. Tool Results Blocks
```
<|tool|>
[Search Results for "weather Tokyo"]

--- #1: Tokyo Weather Forecast ---
url: https://weather.com/tokyo
content: Current temperature is 25°C...

--- #2: Tokyo Climate Data ---
url: https://climate.example.com
content: Average temperature in Tokyo...
<|/tool|>
```

## Visual Design

### Think Block
- **Color Scheme**: Blue gradient (`#f0f4ff` → `#e8f0fe`)
- **Border**: Light blue (`#b8d4ff`)
- **Icon**: Light bulb (💡)
- **Behavior**: 
  - Rounded rectangle (8px radius)
  - Max height: 4 lines
  - Scrollable if content is longer
  - Shows "THINKING" header

### Tool Call Block
- **Color Scheme**: Yellow gradient (`#fff8e1` → `#fff3cd`)
- **Border**: Gold (`#ffd54f`)
- **Icon**: Code brackets (`</>`)
- **Behavior**:
  - Compact one-line display
  - Shows function name and primary argument
  - Example: `search: What is the weather in Tokyo?`
  - Multiple tool calls are connected (no rounded corners where they touch)
  - First call has top rounded corners, last has bottom rounded corners

### Tool Results Block
- **Color Scheme**: Green gradient (`#f1f8e9` → `#e8f5e9`)
- **Border**: Light green (`#aed581`)
- **Icon**: Checkmark (✓)
- **Behavior**:
  - Max height: 4 lines
  - Scrollable if content is longer
  - Shows "RESULTS" header
  - Connected to preceding tool call blocks
  - Standalone mode when no tool calls precede it

## Connection Rules

1. **Tool Call → Tool Call**: Connected, shared border, no rounded corners in between
2. **Tool Call → Tool Results**: Connected, shared border, results follow calls seamlessly
3. **Tool Results → Text**: Tool results has bottom rounded corners
4. **Think Block**: Always standalone with full rounded corners

## Example Message Flow

```
User: What's the weather in Tokyo and Paris?

Agent Response:
<|think|>
I need to search for weather information for both Tokyo and Paris.
I'll use the search tool twice.
<|/think|>

<function=search>
<parameter=query>weather Tokyo current</parameter>
</function>

<function=search>
<parameter=query>weather Paris current</parameter>
</function>

<|tool|>
[Search Results for "weather Tokyo current"]
--- #1: Tokyo Weather ---
Temperature: 25°C, Sunny

[Search Results for "weather Paris current"]
--- #1: Paris Weather ---
Temperature: 18°C, Cloudy
<|/tool|>

Based on the search results:
- **Tokyo**: Currently 25°C and sunny
- **Paris**: Currently 18°C and cloudy
```

**Renders as:**

```
┌─────────────────────────────────────┐
│ 💡 THINKING                         │ Blue box
│ I need to search for weather...     │ (4 lines max,
│ I'll use the search tool twice.     │  scrollable)
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ </> search: weather Tokyo current   │ Yellow box
├─────────────────────────────────────┤ (connected)
│ </> search: weather Paris current   │ Yellow box
├─────────────────────────────────────┤ (connected)
│ ✓ RESULTS                           │ Green box
│ [Search Results...]                 │ (4 lines max,
│ Temperature: 25°C, Sunny...         │  scrollable)
└─────────────────────────────────────┘

Based on the search results:
- **Tokyo**: Currently 25°C and sunny
- **Paris**: Currently 18°C and cloudy
```

## Implementation

### Components

1. **`AgentBlock.jsx`** - Main component library
   - `parseAgentMarkup()` - Parses content with special tags
   - `parseToolContent()` - Extracts tool calls from XML
   - `ThinkBlock` - Renders thinking block
   - `ToolCallBlock` - Renders one-line tool call
   - `ToolResultsBlock` - Renders scrollable results
   - `AgentContent` - Main wrapper component

2. **`AgentBlock.css`** - Styling
   - Gradient backgrounds
   - Scrollbar styling
   - Connection logic
   - Dark mode support

3. **`MessageList.jsx`** - Integration
   - Detects agent markup in messages
   - Routes to `AgentContent` or regular markdown

### Key Functions

#### `parseAgentMarkup(content)`
Parses the entire message content and returns an array of parts:
```javascript
[
  { type: 'text', content: '...' },
  { type: 'think', content: '...' },
  { type: 'tool-call', functionName: 'search', params: {...} },
  { type: 'tool-results', content: '...' },
  { type: 'text', content: '...' }
]
```

#### `parseToolContent(toolContent)`
Extracts function calls and results from tool block:
```javascript
[
  { type: 'tool-call', functionName: 'search', params: {query: '...'}, isFirst: true, isLast: false },
  { type: 'tool-call', functionName: 'extract', params: {url: '...'}, isFirst: false, isLast: true },
  { type: 'tool-results', content: '...' }
]
```

#### `getPrimaryArg(functionName, params)`
Determines which parameter to display in the one-line tool call:
- `search`: Shows `query` parameter
- `extract`: Shows `url` parameter
- Default: First parameter value

## Dark Mode Support

All blocks have dark mode variants:
- **Think**: Dark blue gradient
- **Tool Call**: Dark orange/brown gradient
- **Tool Results**: Dark green gradient

Colors are automatically applied via `@media (prefers-color-scheme: dark)`.

## Styling Details

### Scrollbars
Custom styled scrollbars for think and tool results blocks:
- Width: 6px
- Track: Semi-transparent
- Thumb: Darker, rounded
- Hover: Even darker

### Borders
- Think: Full rounded (8px all corners)
- Tool calls: Top corners rounded on first, bottom on last
- Tool results: No top corners when following tool calls

### Spacing
- Blocks have 8px vertical margin
- First child: No top margin
- Last child: No bottom margin
- Connected blocks: -1px margin to overlap borders

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid and Flexbox
- Custom scrollbar styling (WebKit only, falls back gracefully)

## Testing

Test with different message patterns:

1. **Think only**: `<|think|>...<|/think|>`
2. **Tool calls only**: `<function=...>...</function>`
3. **Mixed**: Think + Tool calls + Results + Text
4. **Long content**: Test 4-line limit and scrolling
5. **Multiple tool calls**: Test connection rendering
6. **Empty blocks**: Should handle gracefully
7. **Malformed markup**: Should fall back to regular text

## Future Enhancements

- [ ] Expand/collapse for long blocks
- [ ] Syntax highlighting for tool parameters
- [ ] Copy button for tool calls
- [ ] Animation when blocks appear
- [ ] Configurable color schemes
- [ ] Export agent trace as JSON

---

**Files Modified:**
- `frontend/src/components/AgentBlock.jsx` (new)
- `frontend/src/components/AgentBlock.css` (new)
- `frontend/src/components/MessageList.jsx` (updated)

**Status:** ✅ Ready for testing

