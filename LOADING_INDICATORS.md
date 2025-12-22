# Improved Loading Indicators

## Changes Made

### 1. ✅ Skeleton Loading Preview (Initial Loading)

**Before:** Three small dots bouncing
```
● ● ●
```

**After:** Skeleton lines with shimmer effect that look like content preview
```
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ (90% width, shimmering)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   (85% width, shimmering)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓       (75% width, shimmering)
```

**Features:**
- 3 skeleton lines of varying widths
- Shimmer animation (gradient moving left to right)
- Looks like text content loading
- Adapts to light/dark mode

### 2. ✅ Inline Streaming Indicator

**Shows after current content during streaming:**
```
Agent response text here... ● ● ●
```

**When waiting for next turn (e.g., after tool call):**
```
┌────────────────────────────────┐
│ search: query text             │
└────────────────────────────────┘
● ● ●  ← Inline loading indicator
```

**Features:**
- Small pulsing dots
- Shows after last content
- Indicates agent is still working
- Appears during streaming pauses

## CSS Implementation

### Skeleton Loading
```css
.skeleton-line {
  height: 16px;
  background: linear-gradient(
    90deg,
    rgba(0, 0, 0, 0.06) 0%,
    rgba(0, 0, 0, 0.12) 50%,
    rgba(0, 0, 0, 0.06) 100%
  );
  background-size: 200% 100%;
  border-radius: 4px;
  animation: shimmer 1.5s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### Inline Loading
```css
.inline-loading-dot {
  width: 4px;
  height: 4px;
  background: currentColor;
  border-radius: 50%;
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  30% {
    opacity: 1;
    transform: scale(1);
  }
}
```

## State Tracking

### Message States
```javascript
{
  isLoading: true,      // Initial loading (shows skeleton)
  isStreaming: true,    // Actively streaming (shows inline dots)
  content: "...",       // Current content
}
```

### State Transitions
```
1. User sends message
   → isLoading: true  → Shows skeleton preview

2. Stream starts (message_start)
   → isLoading: true, isStreaming: true

3. First chunk arrives (message_chunk)
   → isLoading: false, isStreaming: true  → Shows content + inline dots

4. More chunks arrive
   → isStreaming: true  → Content updates + inline dots remain

5. Stream completes (message_complete)
   → isStreaming: false  → Inline dots disappear
```

## Visual Examples

### Initial Loading State
```
User: What is AI?
