# Elegant Agent Block Design

## Design Philosophy

The agent blocks now use a **minimal, elegant design** with:
- ✨ Light gray backgrounds (no bright colors)
- 🚫 No borders
- 📝 Same font and size as normal text
- 👻 Scrollbars that only appear when needed
- 🌓 Perfect for both light and dark modes

## Visual Design

### Light Mode
- **Think Block**: `rgba(0, 0, 0, 0.03)` - Very light gray
- **Tool Call Block**: `rgba(0, 0, 0, 0.04)` - Slightly darker gray
- **Tool Results Block**: `rgba(0, 0, 0, 0.02)` - Lightest gray

### Dark Mode
- **Think Block**: `rgba(255, 255, 255, 0.05)` - Subtle white overlay
- **Tool Call Block**: `rgba(255, 255, 255, 0.06)` - Slightly brighter
- **Tool Results Block**: `rgba(255, 255, 255, 0.04)` - Subtle overlay

## Typography

All blocks now use:
```css
font-family: inherit;  /* Same as your main text */
font-size: inherit;    /* Same as your main text */
line-height: 1.6;      /* Comfortable reading */
```

No more monospace fonts! Everything looks cohesive.

## Scrollbars

Scrollbars are **invisible by default** and only appear when:
1. User hovers over the block
2. User is actively scrolling

```css
/* Hidden by default */
::-webkit-scrollbar-thumb {
  background: transparent;
}

/* Visible on hover */
:hover::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);  /* Light mode */
  background: rgba(255, 255, 255, 0.2);  /* Dark mode */
}

/* Darker when scrolling */
::-webkit-scrollbar-thumb:active {
  background: rgba(0, 0, 0, 0.3);  /* Light mode */
  background: rgba(255, 255, 255, 0.3);  /* Dark mode */
}
```

## Layout

### Spacing
- Blocks: `10px` vertical margin
- Rounded corners: `6px` radius
- Padding: `12-16px`

### Tool Call Groups
Consecutive tool calls have minimal spacing:
```
┌──────────────────────────────┐
│ search: AI developments       │ ← 1px gap
├──────────────────────────────┤
│ extract: https://example.com  │
└──────────────────────────────┘
```

## Example Appearance

### Light Mode
```
Regular text here...

╔══════════════════════════════╗
║ This is a think block with   ║  ← Light gray (3% black)
║ some reasoning content...    ║
╚══════════════════════════════╝

More text...

╔══════════════════════════════╗
║ search: query text           ║  ← Slightly darker gray (4% black)
║ extract: url here            ║
╚══════════════════════════════╝

╔══════════════════════════════╗
║ Results from the search      ║  ← Lightest gray (2% black)
║ Content here...              ║
╚══════════════════════════════╝

Final text...
```

### Dark Mode
```
Regular text here...

╔══════════════════════════════╗
║ This is a think block with   ║  ← Light white overlay (5%)
║ some reasoning content...    ║
╚══════════════════════════════╝

More text...

╔══════════════════════════════╗
║ search: query text           ║  ← Slightly brighter (6%)
║ extract: url here            ║
╚══════════════════════════════╝

╔══════════════════════════════╗
║ Results from the search      ║  ← Subtle white overlay (4%)
║ Content here...              ║
╚══════════════════════════════╝

Final text...
```

## Accessibility

### Contrast Ratios
- Light mode: Sufficient contrast with subtle backgrounds
- Dark mode: Readable with white overlays
- Text: Inherits main text color (excellent contrast)

### Visual Hierarchy
1. **Think blocks**: Slightly darker - shows internal reasoning
2. **Tool calls**: Most visible - shows actions taken
3. **Tool results**: Lightest - shows data/outputs

## Benefits

✅ **Elegant**: No harsh colors or borders  
✅ **Cohesive**: Matches your main text style  
✅ **Readable**: Same fonts and sizes  
✅ **Clean**: Scrollbars hidden until needed  
✅ **Adaptive**: Works perfectly in light and dark modes  
✅ **Professional**: Subtle backgrounds instead of bright colors  

## CSS Summary

### Key Properties
```css
/* No borders */
border: none;

/* Subtle backgrounds */
background: rgba(0, 0, 0, 0.02-0.04);  /* Light */
background: rgba(255, 255, 255, 0.04-0.06);  /* Dark */

/* Inherited typography */
font-family: inherit;
font-size: inherit;
line-height: 1.6;

/* Hidden scrollbars */
scrollbar-thumb: transparent (default)
scrollbar-thumb: visible (on hover/scroll)
```

### Block Types
| Block Type | Light Mode | Dark Mode | Max Height |
|------------|------------|-----------|------------|
| Think | 3% black | 5% white | 5 lines |
| Tool Call | 4% black | 6% white | 1 line |
| Tool Results | 2% black | 4% white | 5 lines |

## Implementation Details

### Opacity Layers
The design uses opacity to automatically adapt to any background:
- Works with white backgrounds
- Works with dark backgrounds
- Works with colored backgrounds
- Maintains text readability

### Icon Styling
Icons in tool calls are subtle:
```css
opacity: 0.6;  /* Slightly faded */
```

### Text Opacity
Tool call arguments are slightly faded for hierarchy:
```css
opacity: 0.75;  /* Secondary information */
```

## Comparison

### Before (Colorful)
- 🔵 Blue gradient for think
- 🟡 Yellow gradient for tool calls
- 🟢 Green gradient for results
- 📦 Visible borders
- 📏 Monospace fonts
- 📜 Always-visible scrollbars

### After (Elegant)
- ⚪ Light gray backgrounds
- 🚫 No borders
- 📝 Same font as main text
- 👻 Hidden scrollbars
- 🎨 Adapts to light/dark mode
- ✨ Professional appearance

---

**Status:** ✅ Implemented
**Design System:** Minimal, elegant, cohesive

