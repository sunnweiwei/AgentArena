# Final Agent UI Design

## Design Philosophy

The agent blocks now **match the chat interface** with colors that relate to user message backgrounds.

## Key Features

### 1. ✅ Think Blocks - Collapsed by Default
```
Thought ►          ← Click to expand (default state)
```

**Expanded:**
```
Thought ▼          ← Click to collapse
  Reasoning content here...
  Up to 5 lines with scrolling
```

### 2. ✅ Tool Box Colors Match User Messages

**Light Mode:**
- **Tool Call**: `#f1f2f5` (same as user message background)
- **Tool Results**: `#f8f9fa` (lighter, between user and assistant)
- **Assistant Message**: `#ffffff` (white)

**Color Hierarchy:**
```
User Message:      #f1f2f5 (darker gray)
Tool Call Box:     #f1f2f5 (same as user - notable)
Tool Results Box:  #f8f9fa (in between - lighter)
Assistant Message: #ffffff (white - lightest)
```

**Dark Mode:**
- **Tool Call**: `rgba(255, 255, 255, 0.12)` (whiter than normal)
- **Tool Results**: `rgba(255, 255, 255, 0.06)` (in between)
- **Assistant Message**: Normal background

**Color Hierarchy:**
```
Tool Call Box:     12% white (most visible)
Tool Results Box:  6% white (in between)
Assistant Message: Normal dark background
```

### 3. ✅ Tool Results - Smaller Font, 6 Lines
- Font size: `0.9em` (same as think blocks)
- Max lines: **6 lines** (increased from 5)
- Scrollable when longer

## Visual Example

### Light Mode
```
Assistant: Let me search for that information.

Thought ►                    ← Collapsed by default, click to expand

I'll search for AI news:

┌────────────────────────────────┐
│ search: AI developments 2024   │  ← #f1f2f5 (user message color)
├────────────────────────────────┤  Connected
│ [Search Results...]            │  ← #f8f9fa (lighter, 90% font, 6 lines)
│ Found relevant articles...     │
│ Top result from Tech News      │
└────────────────────────────────┘

Based on the results above...
```

### Dark Mode
```
Assistant: Let me search for that information.

Thought ►                    ← Collapsed by default, click to expand

I'll search for AI news:

┌────────────────────────────────┐
│ search: AI developments 2024   │  ← 12% white (very visible)
├────────────────────────────────┤  Connected
│ [Search Results...]            │  ← 6% white (in between, 90% font, 6 lines)
│ Found relevant articles...     │
│ Top result from Tech News      │
└────────────────────────────────┘

Based on the results above...
```

## Color Rationale

### Why Match User Message Color?

Tool calls are **actions initiated by the agent** (similar to user input), so they share the same visual weight and background color as user messages.

### Why Tool Results Are Lighter?

Tool results are **passive information** (like assistant output), so they use a lighter color that's between the active tool call and the main assistant response.

### Why Darker in Dark Mode?

In dark mode, lighter backgrounds stand out more. Tool calls get 12% white to be very visible, while results get 6% white to be subtle but still distinct.

## Typography

### Think Blocks
```css
font-size: 0.9em;        /* 90% of normal */
opacity: 0.7;            /* Subdued */
max-lines: 5;            /* Scrollable */
default: collapsed;      /* Saves space */
```

### Tool Results
```css
font-size: 0.9em;        /* 90% of normal - same as think */
opacity: 0.85;           /* Slightly more prominent */
max-lines: 6;            /* One more line than think */
```

### Tool Call Names
```css
font-size: inherit;      /* Normal size */
font-weight: 500;        /* Medium weight */
opacity: 1.0;            /* Full opacity */
```

## Complete Color Matrix

### Light Mode
| Element | Background | Purpose |
|---------|-----------|---------|
| User Message | `#f1f2f5` | User input |
| **Tool Call** | `#f1f2f5` | Agent action (same as user) |
| **Tool Results** | `#f8f9fa` | Retrieved data (in between) |
| Assistant Message | `#ffffff` | Agent response |

### Dark Mode
| Element | Background | Purpose |
|---------|-----------|---------|
| **Tool Call** | `12% white` | Agent action (very visible) |
| **Tool Results** | `6% white` | Retrieved data (moderate) |
| Assistant Message | Normal | Agent response |

## Interaction States

### Think Block
```javascript
State: isCollapsed = true  // Default
Click: Toggle collapse/expand
Animation: Smooth 0.3s fade
```

### Tool Call Box
```javascript
Hover: No change (static)
Click: No action (informational)
Connection: Connects to tool results below
```

### Tool Results Box
```javascript
Hover: Scrollbar appears
Scroll: Content scrolls within max-height
Connection: Connects to tool calls above
```

## Design Benefits

✅ **Collapsed by default** - Saves space, reduces clutter  
✅ **Color continuity** - Tool calls match user message aesthetic  
✅ **Visual hierarchy** - Tool call → Tool results → Response  
✅ **Readable** - Smaller font for secondary info (think, results)  
✅ **Consistent** - Works with existing chat design  
✅ **Dark mode optimized** - Whiter boxes stand out appropriately  
✅ **More content** - 6 lines for tool results (vs 5)  

## CSS Summary

```css
/* Light Mode */
.agent-block.tool-call {
  background: #f1f2f5;  /* User message color */
}

.agent-block.tool-results {
  background: #f8f9fa;  /* Between user and assistant */
  font-size: 0.9em;
  max-height: calc(0.9em * 1.6 * 6 + 24px);  /* 6 lines */
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
  .agent-block.tool-call {
    background: rgba(255, 255, 255, 0.12);  /* Notable */
  }
  
  .agent-block.tool-results {
    background: rgba(255, 255, 255, 0.06);  /* Subtle */
  }
}
```

## Comparison: Before vs After

### Before
- Think: Always expanded
- Tool calls: Generic gray (8% black / 12% white)
- Tool results: Different gray (4% black / 8% white)
- Tool results: Normal font size, 5 lines

### After
- Think: ✨ **Collapsed by default**
- Tool calls: ✨ **User message color** (#f1f2f5 / 12% white)
- Tool results: ✨ **In-between color** (#f8f9fa / 6% white)
- Tool results: ✨ **Smaller font (0.9em), 6 lines**

## Example Conversation

```
User: What are the latest AI developments?
