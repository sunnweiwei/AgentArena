# Tool Call Extraction Examples

## How It Works

The frontend now automatically detects and displays tool calls (`<function=...>`) anywhere in the message content as visual boxes.

## Example 1: Extract Tool Call in Normal Content

**Agent Response:**
```
Based on your question, I'll extract information from the AI Index report.

<function=extract>
<parameter=url>https://hai.stanford.edu/ai-index/2025-ai-index-report</parameter>
<parameter>major findings 2024 AI models geography trends 2025</parameter>
</function>

Let me analyze the findings from this report...
```

**Displays as:**
```
Based on your question, I'll extract information from the AI Index report.

┌─────────────────────────────────────────────────────────────┐
│ </> extract: https://hai.stanford.edu/ai-index/2025-ai-...  │ ← Yellow box
└─────────────────────────────────────────────────────────────┘

Let me analyze the findings from this report...
```

## Example 2: Multiple Tool Calls (Connected)

**Agent Response:**
```
I'll search for information about AI developments.

<function=search>
<parameter=query>AI developments 2024</parameter>
<parameter=max_results>5</parameter>
</function>

<function=extract>
<parameter=url>https://example.com/ai-news</parameter>
</function>

Now analyzing the results...
```

**Displays as:**
```
I'll search for information about AI developments.

┌─────────────────────────────────────────────────────────────┐
│ </> search: AI developments 2024                             │ ← Yellow box (connected)
├─────────────────────────────────────────────────────────────┤
│ </> extract: https://example.com/ai-news                     │ ← Yellow box (connected)
└─────────────────────────────────────────────────────────────┘

Now analyzing the results...
```

## Example 3: Complete Agent Flow

**Agent Response:**
```
<|think|>
I need to find the latest AI Index report and extract key findings.
I'll search first to find the URL, then extract the content.
<|/think|>

Let me search for the report.

<function=search>
<parameter=query>Stanford AI Index 2025 report</parameter>
</function>

<|tool|>
[Search Results for "Stanford AI Index 2025 report"]
--- #1: Stanford HAI - AI Index 2025 ---
url: https://hai.stanford.edu/ai-index/2025-ai-index-report
content: The 2025 AI Index Report tracks AI progress globally...
<|/tool|>

Great! Now I'll extract the detailed findings.

<function=extract>
<parameter=url>https://hai.stanford.edu/ai-index/2025-ai-index-report</parameter>
</function>

<|tool|>
[Page Content]
The AI Index 2025 Report highlights:
- 45% increase in AI model capabilities
- Geographic shift in AI development
- Emerging trends in multimodal AI
<|/tool|>

Based on the extracted information, here are the major findings...
```

**Displays as:**
```
┌─────────────────────────────────────────────────────────────┐
│ I need to find the latest AI Index report and extract key   │ ← Blue think box
│ findings. I'll search first to find the URL, then extract   │   (5 lines max)
│ the content.                                                 │
└─────────────────────────────────────────────────────────────┘

Let me search for the report.

┌─────────────────────────────────────────────────────────────┐
│ </> search: Stanford AI Index 2025 report                    │ ← Yellow tool call
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ [Search Results for "Stanford AI Index 2025 report"]        │ ← Green results box
│ --- #1: Stanford HAI - AI Index 2025 ---                    │   (5 lines max)
│ url: https://hai.stanford.edu/ai-index/2025-ai-index-report │
│ content: The 2025 AI Index Report tracks AI progress...     │
└─────────────────────────────────────────────────────────────┘

Great! Now I'll extract the detailed findings.

┌─────────────────────────────────────────────────────────────┐
│ </> extract: https://hai.stanford.edu/ai-index/2025-ai-...  │ ← Yellow tool call
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ [Page Content]                                               │ ← Green results box
│ The AI Index 2025 Report highlights:                         │   (5 lines max)
│ - 45% increase in AI model capabilities                      │
│ - Geographic shift in AI development                         │
│ - Emerging trends in multimodal AI                           │
└─────────────────────────────────────────────────────────────┘

Based on the extracted information, here are the major findings...
```

## Parameter Handling

### Named Parameters
```xml
<function=search>
<parameter=query>AI trends</parameter>
<parameter=max_results>10</parameter>
</function>
```
**Displays:** `search: AI trends`

### Unnamed Parameters
```xml
<function=extract>
<parameter=url>https://example.com</parameter>
<parameter>key findings summary</parameter>
</function>
```
**Displays:** `extract: https://example.com`

### Mixed Parameters
```xml
<function=custom_tool>
<parameter=input>some data</parameter>
<parameter>additional info</parameter>
</function>
```
**Displays:** `custom_tool: some data`

## Visual Rules

### Think Blocks (`<|think|>`)
- **Color:** Blue gradient
- **Style:** Rounded rectangle, standalone
- **Max height:** 5 lines, scrollable
- **Margin:** 8px top and bottom

### Tool Call Boxes (`<function=...>`)
- **Color:** Yellow gradient
- **Style:** One line, compact
- **Display:** `function_name: primary_argument`
- **Connection:** Multiple consecutive calls are connected (shared borders)
- **Margin:** 8px for the group, not individual boxes

### Tool Results Blocks (`<|tool|>`)
- **Color:** Green gradient
- **Style:** Rounded rectangle, standalone
- **Max height:** 5 lines, scrollable
- **Margin:** 8px top and bottom

## Implementation Notes

### Detection
The parser looks for these patterns anywhere in the content:
- `<|think|>...</|think|>` → Think block
- `<|tool|>...</|tool|>` → Tool results block
- `<function=...>...</function>` → Tool call box
- Everything else → Normal markdown text

### Grouping
Consecutive tool calls are automatically grouped and connected:
- First call: top rounded corners
- Middle calls: no rounded corners, shared borders
- Last call: bottom rounded corners

### Primary Argument Selection
- `search`: Shows `query` parameter
- `extract`: Shows `url` parameter
- Others: Shows first named parameter or first unnamed parameter

## Browser Testing

Test these scenarios:
1. ✅ Single tool call in text
2. ✅ Multiple consecutive tool calls (should connect)
3. ✅ Tool calls separated by text (should be separate boxes)
4. ✅ Long URLs (should truncate with ellipsis)
5. ✅ Missing parameters (should show empty or fallback)
6. ✅ Mixed with think blocks and tool results
7. ✅ Scrolling in think/results blocks (5+ lines)

---

**Status:** ✅ Implemented and ready for use

