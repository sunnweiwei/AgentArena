# Streaming Example: Create Elon Musk HTML Page

## User Request
```
"Create an HTML page introducing Elon Musk with a nice design"
```

## Model Used
`gpt-5-nano` (configured in config.py)

---

## Streaming Output (Chunk by Chunk)

### Chunk 1: Initial Thinking
```json
{
  "type": "thinking",
  "content": "Step 1: Agent is thinking..."
}
```
**What happens**: Agent receives the task and starts processing

---

### Chunk 2: First Action - Create HTML File
```json
{
  "type": "action",
  "action": "Using tool: str_replace_based_edit_tool",
  "tool": "str_replace_based_edit_tool",
  "arguments": {
    "path": "elon_musk.html",
    "old_str": "",
    "new_str": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Elon Musk - Visionary Entrepreneur</title>\n    <style>\n        * {\n            margin: 0;\n            padding: 0;\n            box-sizing: border-box;\n        }\n        body {\n            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;\n            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n            min-height: 100vh;\n            padding: 20px;\n        }\n        .container {\n            max-width: 800px;\n            margin: 0 auto;\n            background: white;\n            border-radius: 20px;\n            box-shadow: 0 20px 60px rgba(0,0,0,0.3);\n            overflow: hidden;\n        }\n        .header {\n            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);\n            color: white;\n            padding: 60px 40px;\n            text-align: center;\n        }\n        .header h1 {\n            font-size: 3em;\n            margin-bottom: 10px;\n        }\n        .header p {\n            font-size: 1.2em;\n            opacity: 0.9;\n        }\n        .content {\n            padding: 40px;\n        }\n        .section {\n            margin-bottom: 30px;\n        }\n        .section h2 {\n            color: #2a5298;\n            margin-bottom: 15px;\n            font-size: 1.8em;\n        }\n        .section p {\n            line-height: 1.8;\n            color: #333;\n            font-size: 1.1em;\n        }\n        .achievements {\n            display: grid;\n            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));\n            gap: 20px;\n            margin-top: 20px;\n        }\n        .achievement-card {\n            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n            color: white;\n            padding: 20px;\n            border-radius: 10px;\n            text-align: center;\n        }\n        .achievement-card h3 {\n            margin-bottom: 10px;\n        }\n    </style>\n</head>\n<body>\n    <div class=\"container\">\n        <div class=\"header\">\n            <h1>Elon Musk</h1>\n            <p>Entrepreneur, Engineer, Visionary</p>\n        </div>\n        <div class=\"content\">\n            <div class=\"section\">\n                <h2>About</h2>\n                <p>Elon Musk is a business magnate, industrial designer, and engineer. He is the founder, CEO, and Chief Engineer at SpaceX; early-stage investor, CEO, and Product Architect of Tesla, Inc.; founder of The Boring Company; and co-founder of Neuralink and OpenAI.</p>\n            </div>\n            <div class=\"section\">\n                <h2>Vision</h2>\n                <p>Musk's vision includes reducing global warming through sustainable energy production and consumption, and reducing the risk of human extinction by establishing a human colony on Mars.</p>\n            </div>\n            <div class=\"section\">\n                <h2>Key Achievements</h2>\n                <div class=\"achievements\">\n                    <div class=\"achievement-card\">\n                        <h3>SpaceX</h3>\n                        <p>Revolutionary space exploration</p>\n                    </div>\n                    <div class=\"achievement-card\">\n                        <h3>Tesla</h3>\n                        <p>Electric vehicle innovation</p>\n                    </div>\n                    <div class=\"achievement-card\">\n                        <h3>Neuralink</h3>\n                        <p>Brain-computer interface</p>\n                    </div>\n                    <div class=\"achievement-card\">\n                        <h3>The Boring Company</h3>\n                        <p>Infrastructure tunneling</p>\n                    </div>\n                </div>\n            </div>\n        </div>\n    </div>\n</body>\n</html>",
    "create_file": true
  },
  "reasoning": "I'll create a modern, visually appealing HTML page about Elon Musk with a gradient design, clean layout, and information about his achievements."
}
```
**What happens**: Agent decides to create the HTML file with a complete design

---

### Chunk 3: Observation - File Created
```json
{
  "type": "observation",
  "tool": "str_replace_based_edit_tool",
  "result": "File created successfully at elon_musk.html",
  "success": true
}
```
**What happens**: Tool confirms the file was created

---

### Chunk 4: Thinking - Verify Creation
```json
{
  "type": "thinking",
  "content": "Step 2: Agent is thinking..."
}
```
**What happens**: Agent considers next steps

---

### Chunk 5: Action - List Files to Verify
```json
{
  "type": "action",
  "action": "Using tool: bash",
  "tool": "bash",
  "arguments": {
    "command": "ls -lh elon_musk.html"
  },
  "reasoning": "Let me verify the file was created successfully."
}
```
**What happens**: Agent wants to confirm the file exists

---

### Chunk 6: Observation - File Verified
```json
{
  "type": "observation",
  "tool": "bash",
  "result": "-rw-r--r-- 1 user user 3.2K Nov 23 19:58 elon_musk.html",
  "success": true
}
```
**What happens**: File exists and is 3.2KB in size

---

### Chunk 7: Thinking - Consider Preview
```json
{
  "type": "thinking",
  "content": "Step 3: Agent is thinking..."
}
```
**What happens**: Agent considers if anything else is needed

---

### Chunk 8: Action - Show File Preview
```json
{
  "type": "action",
  "action": "Using tool: bash",
  "tool": "bash",
  "arguments": {
    "command": "head -20 elon_musk.html"
  },
  "reasoning": "Let me show a preview of the HTML file to confirm it has the proper structure."
}
```
**What happens**: Agent wants to show a preview of the file

---

### Chunk 9: Observation - Preview Content
```json
{
  "type": "observation",
  "tool": "bash",
  "result": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Elon Musk - Visionary Entrepreneur</title>\n    <style>\n        * {\n            margin: 0;\n            padding: 0;\n            box-sizing: border-box;\n        }\n        body {\n            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;\n            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n            min-height: 100vh;\n            padding: 20px;\n        }\n        .container {",
  "success": true
}
```
**What happens**: Shows the beginning of the HTML file

---

### Chunk 10: Final Response
```json
{
  "type": "response",
  "content": "I've successfully created an HTML page introducing Elon Musk! The page features:\n\n✅ **Modern Design**: Beautiful gradient background (purple to blue)\n✅ **Responsive Layout**: Works on all devices\n✅ **Clean Structure**: Header with title, content sections\n✅ **Information Sections**:\n   - About: Brief introduction\n   - Vision: His goals for humanity\n   - Key Achievements: Cards for SpaceX, Tesla, Neuralink, and The Boring Company\n\n✅ **Styling**: Professional CSS with gradients, shadows, and modern typography\n\nThe file is saved as `elon_musk.html` (3.2KB) and is ready to open in any web browser!",
  "finished": true
}
```
**What happens**: Agent provides a summary of what was accomplished

---

### Chunk 11: Stream Complete
```json
{
  "type": "done"
}
```
**What happens**: Stream ends

---

## Timeline Visualization

```
Time    Event Type      What User Sees
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
0.0s    thinking        💭 "Agent is thinking..."
0.5s    action          🔧 Creating file: elon_musk.html
                           Tool: str_replace_based_edit_tool
1.2s    observation     ✅ File created successfully
1.5s    thinking        💭 "Agent is thinking..."
1.8s    action          🔧 Verifying file: ls -lh elon_musk.html
2.0s    observation     ✅ File size: 3.2KB
2.2s    thinking        💭 "Agent is thinking..."
2.5s    action          🔧 Showing preview: head -20 elon_musk.html
2.8s    observation     ✅ Preview: <!DOCTYPE html>...
3.0s    response        ✨ Task completed! HTML page created with...
3.1s    done            🏁 Stream ended
```

---

## Frontend Display Example

### What User Sees (Real-time Updates)

**At 0.5s:**
```
💭 Agent is thinking...
🔧 Creating HTML file for Elon Musk...
```

**At 1.2s:**
```
💭 Agent is thinking...
🔧 Creating HTML file for Elon Musk...
✅ File created successfully
```

**At 2.0s:**
```
💭 Agent is thinking...
🔧 Creating HTML file for Elon Musk...
✅ File created successfully
🔧 Verifying file...
✅ File verified (3.2KB)
```

**At 2.8s:**
```
💭 Agent is thinking...
🔧 Creating HTML file for Elon Musk...
✅ File created successfully
🔧 Verifying file...
✅ File verified (3.2KB)
🔧 Showing preview...
✅ Preview loaded
```

**At 3.0s (Final):**
```
✨ Task Completed!

I've successfully created an HTML page introducing Elon Musk!

✅ Modern Design: Beautiful gradient background
✅ Responsive Layout: Works on all devices
✅ Information Sections: About, Vision, Achievements
✅ File: elon_musk.html (3.2KB)

Ready to open in your browser!
```

---

## Code to Receive These Chunks

### Python
```python
import requests
import json

session_id = "abc-123..."  # From session creation

with requests.post(
    f"http://sf.lti.cs.cmu.edu:8001/sessions/{session_id}/prompt",
    json={
        "prompt": "Create an HTML page introducing Elon Musk with a nice design",
        "stream": True
    },
    stream=True
) as response:
    for line in response.iter_lines():
        if line and line.startswith(b'data: '):
            chunk = json.loads(line[6:])
            
            # Each chunk is one of the events shown above
            print(f"[{chunk['type']}]", chunk)
```

### JavaScript
```javascript
const response = await fetch(url, {
    method: 'POST',
    body: JSON.stringify({
        prompt: "Create an HTML page introducing Elon Musk with a nice design",
        stream: true
    })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const event = JSON.parse(line.slice(6));
            
            // Each event is one of the chunks shown above
            console.log(`[${event.type}]`, event);
            updateUI(event);  // Update your UI in real-time
        }
    }
}
```

---

## Summary

**Total Chunks**: 11 events
**Total Time**: ~3 seconds
**Actions Taken**: 3 (create file, verify, preview)
**Observations**: 3 (one per action)
**Final Result**: Beautiful HTML page about Elon Musk

The streaming API lets your frontend show **real-time progress** instead of a loading spinner! 🎉
