# Canvas/Whiteboard Feature

## Overview
A canvas/whiteboard mode that displays alongside the chat interface, providing a visual workspace for displaying content, diagrams, or other visual elements.

## Features

### 1. Canvas Toggle Button
- **Location**: Top bar header, right section, left of the "Connected" status indicator
- **Icon**: Grid icon (representing canvas/whiteboard)
- **States**: 
  - Default: Transparent background, secondary text color
  - Hover: Secondary background, primary text color
  - Active: Accent color when canvas is open

### 2. Canvas Panel - Desktop (>1024px)
- **Layout**: Appears on the right side of the chat interface
- **Size**: Default 50% width, **resizable by dragging the divider**
- **Resize Range**: Between 20% and 80% of screen width
- **Design**: Rounded rectangle with user message background color, no border, subtle shadow
- **Height**: Full height, same as message list
- **Input Bar**: Positioned only under the message list (left side), width adjusts with resize

### 3. Canvas Panel - Mobile (<1024px)
- **Layout**: Floats above the message list (fixed position, centered)
- **Size**: Same width as message list (max 768px, with 16px padding on sides)
- **Design**: Transparent background with blur effect (glassmorphism)
- **Overlay**: No dark overlay - messages remain visible and unaffected below
- **Height**: Full height from header to bottom
- **Input Bar**: Full width (normal behavior)

### 4. Layout Behavior

**Desktop - Canvas Open:**
```
┌──────────────┃┬──────────────┐
│   Messages   ┃│    Canvas    │
│     50%      ┃│     50%      │
│              ┃│              │
└INPUT─────────┃└──────────────┘
    (50% width) ↑ Draggable divider
    
User can drag divider to resize (20%-80%)
```

**Desktop - Canvas Closed:**
```
┌────────────────────────────┐
│         Messages           │
│           100%             │
│                            │
└─────────INPUT──────────────┘
          (centered)
```

**Mobile - Canvas Open:**
```
┌────────────────────────────┐
│      Messages Below        │
│  ┌──────────────────┐      │
│  │  Canvas (Float)  │      │
│  │  Blur+Transparent│      │
│  │  (Same width as  │      │
│  │   messages)      │      │
│  └──────────────────┘      │
│    Messages visible below  │
└────────────INPUT───────────┘
     (full width)
```

## Implementation Details

### State Management
```javascript
const [canvasOpen, setCanvasOpen] = useState(false)
const [splitRatio, setSplitRatio] = useState(50) // Percentage for left panel
const [isDragging, setIsDragging] = useState(false)
```

### CSS Classes
- `.canvas-toggle-button` - Toggle button styling
- `.canvas-toggle-button.active` - Active state
- `.canvas-panel` - Panel container (side-by-side on desktop, floating on mobile)
- `.canvas-container` - Inner canvas area (rounded rectangle, no border)
- `.canvas-overlay` - Dark overlay on mobile (clickable to close)
- `.resize-handle` - Draggable divider between panels
- `.resize-handle-line` - Visual line indicator for resize handle
- `.chat-body.with-canvas` - Modified layout when canvas is open
- `.chat-content` - Chat messages container (dynamic width based on split)
- `.message-input-wrapper.with-canvas` - Input bar container (dynamic width based on split)

### Component Structure
```jsx
<div className={`chat-body ${canvasOpen ? 'with-canvas' : ''}`}>
  <div className="chat-content">
    {/* Chat messages */}
  </div>
  {canvasOpen && (
    <>
      <div className="canvas-overlay" onClick={() => setCanvasOpen(false)} />
      <div className="canvas-panel">
        <div className="canvas-container">
          {/* Canvas content will go here */}
        </div>
      </div>
    </>
  )}
</div>
<div className={`message-input-wrapper ${canvasOpen ? 'with-canvas' : ''}`}>
  <MessageInput ... />
</div>
```

## Features Completed
- ✅ Canvas toggle button
- ✅ Side-by-side layout on desktop
- ✅ Floating layout on mobile
- ✅ **Resizable split with drag handle**
- ✅ Dynamic input bar positioning

## Future Enhancements
- Canvas content rendering (diagrams, images, etc.)
- Interactive drawing capabilities
- Content synchronization with chat messages
- Export/save canvas content
- Persist split ratio in localStorage

## Files Modified
- `/frontend/src/components/ChatWindow.jsx` - Added canvas state and UI
- `/frontend/src/components/ChatWindow.css` - Added canvas styling and layout

