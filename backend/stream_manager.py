"""
Stream Manager - Keeps agent streams running in background and allows multiple clients to monitor them.

Key features:
- Streams run independently of WebSocket connections
- Accumulated content stored in memory
- Multiple clients can subscribe to same stream
- Clients receive all accumulated content on subscribe
- Saves to database only when stream completes
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Set, Optional, Callable
from fastapi import WebSocket
from datetime import datetime


class StreamState:
    """Represents an active stream"""
    def __init__(self, stream_id: str, chat_id: str, user_id: int):
        self.stream_id = stream_id
        self.chat_id = chat_id
        self.user_id = user_id
        self.accumulated_content = ""
        self.meta_info_updates = []
        self.subscribers: Set[WebSocket] = set()
        self.is_complete = False
        self.is_cancelled = False
        self.error: Optional[str] = None
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.lock = asyncio.Lock()
        self.task: Optional[asyncio.Task] = None
        
    async def add_chunk(self, content: str):
        """Add content chunk and notify all subscribers"""
        async with self.lock:
            self.accumulated_content += content
            # Notify all subscribers
            for ws in list(self.subscribers):
                try:
                    await ws.send_json({
                        "type": "message_chunk",
                        "content": content,
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send chunk to subscriber: {e}")
                    self.subscribers.discard(ws)
    
    async def add_meta_info(self, info: str):
        """Add meta info update and notify all subscribers"""
        async with self.lock:
            self.meta_info_updates.append(info)
            # Notify all subscribers
            for ws in list(self.subscribers):
                try:
                    await ws.send_json({
                        "type": "meta_info_update",
                        "content": info,
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send meta info to subscriber: {e}")
                    self.subscribers.discard(ws)
    
    async def mark_complete(self):
        """Mark stream as complete and notify all subscribers"""
        async with self.lock:
            self.is_complete = True
            self.end_time = time.time()
            duration = self.end_time - self.start_time
            print(f"[StreamState] Stream {self.stream_id} completed in {duration:.2f}s")
            # Notify all subscribers
            for ws in list(self.subscribers):
                try:
                    await ws.send_json({
                        "type": "message_complete",
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send complete notification: {e}")
                    self.subscribers.discard(ws)
    
    async def mark_error(self, error: str):
        """Mark stream as errored and notify all subscribers"""
        async with self.lock:
            self.error = error
            self.is_complete = True
            self.end_time = time.time()
            # Notify all subscribers
            for ws in list(self.subscribers):
                try:
                    await ws.send_json({
                        "type": "error",
                        "message": error,
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send error to subscriber: {e}")
                    self.subscribers.discard(ws)
    
    async def subscribe(self, websocket: WebSocket):
        """Subscribe a WebSocket client and send all accumulated content"""
        async with self.lock:
            self.subscribers.add(websocket)
            
            # Send message_start if not already sent
            try:
                await websocket.send_json({
                    "type": "message_start",
                    "role": "assistant",
                    "stream_id": self.stream_id,
                    "chat_id": self.chat_id
                })
            except Exception as e:
                print(f"[StreamState] Failed to send message_start: {e}")
                self.subscribers.discard(websocket)
                return
            
            # Send all accumulated content
            if self.accumulated_content:
                try:
                    await websocket.send_json({
                        "type": "message_chunk",
                        "content": self.accumulated_content,
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send accumulated content: {e}")
                    self.subscribers.discard(websocket)
                    return
            
            # Send all meta info updates
            for info in self.meta_info_updates:
                try:
                    await websocket.send_json({
                        "type": "meta_info_update",
                        "content": info,
                        "stream_id": self.stream_id,
                        "chat_id": self.chat_id
                    })
                except Exception as e:
                    print(f"[StreamState] Failed to send meta info: {e}")
                    # Continue with other updates
            
            # If stream is complete, send complete notification
            if self.is_complete:
                try:
                    if self.error:
                        await websocket.send_json({
                            "type": "error",
                            "message": self.error,
                            "stream_id": self.stream_id,
                            "chat_id": self.chat_id
                        })
                    else:
                        await websocket.send_json({
                            "type": "message_complete",
                            "stream_id": self.stream_id,
                            "chat_id": self.chat_id
                        })
                except Exception as e:
                    print(f"[StreamState] Failed to send completion status: {e}")
                    self.subscribers.discard(websocket)
    
    def unsubscribe(self, websocket: WebSocket):
        """Unsubscribe a WebSocket client"""
        self.subscribers.discard(websocket)
    
    def cancel(self):
        """Cancel the stream"""
        self.is_cancelled = True
        if self.task and not self.task.done():
            self.task.cancel()


class StreamManager:
    """Manages active streams"""
    def __init__(self):
        self.streams: Dict[str, StreamState] = {}
        self.chat_to_stream: Dict[str, str] = {}  # chat_id -> active stream_id
        self.lock = asyncio.Lock()
        self.cleanup_task: Optional[asyncio.Task] = None
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_old_streams())
    
    async def _cleanup_old_streams(self):
        """Clean up completed streams after a delay"""
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            async with self.lock:
                to_remove = []
                current_time = time.time()
                for stream_id, state in self.streams.items():
                    # Remove completed streams after 1 hour
                    if state.is_complete and state.end_time:
                        if current_time - state.end_time > 3600:
                            to_remove.append(stream_id)
                
                for stream_id in to_remove:
                    print(f"[StreamManager] Cleaning up old stream: {stream_id}")
                    state = self.streams[stream_id]
                    # Remove from chat_to_stream mapping
                    if state.chat_id in self.chat_to_stream:
                        if self.chat_to_stream[state.chat_id] == stream_id:
                            del self.chat_to_stream[state.chat_id]
                    del self.streams[stream_id]
    
    async def create_stream(self, stream_id: str, chat_id: str, user_id: int) -> StreamState:
        """Create a new stream"""
        async with self.lock:
            state = StreamState(stream_id, chat_id, user_id)
            self.streams[stream_id] = state
            self.chat_to_stream[chat_id] = stream_id
            print(f"[StreamManager] Created stream {stream_id} for chat {chat_id}")
            return state
    
    async def get_stream(self, stream_id: str) -> Optional[StreamState]:
        """Get a stream by ID"""
        async with self.lock:
            return self.streams.get(stream_id)
    
    async def get_active_stream_for_chat(self, chat_id: str) -> Optional[StreamState]:
        """Get active stream for a chat"""
        async with self.lock:
            stream_id = self.chat_to_stream.get(chat_id)
            if stream_id:
                state = self.streams.get(stream_id)
                if state and not state.is_complete:
                    return state
            return None
    
    async def subscribe(self, stream_id: str, websocket: WebSocket) -> bool:
        """Subscribe to a stream"""
        state = await self.get_stream(stream_id)
        if state:
            await state.subscribe(websocket)
            return True
        return False
    
    async def unsubscribe(self, stream_id: str, websocket: WebSocket):
        """Unsubscribe from a stream"""
        state = await self.get_stream(stream_id)
        if state:
            state.unsubscribe(websocket)
    
    async def cancel_stream(self, stream_id: str):
        """Cancel a stream"""
        state = await self.get_stream(stream_id)
        if state:
            state.cancel()
            print(f"[StreamManager] Cancelled stream {stream_id}")
    
    async def remove_stream(self, stream_id: str):
        """Remove a stream"""
        async with self.lock:
            state = self.streams.get(stream_id)
            if state:
                # Remove from chat_to_stream mapping
                if state.chat_id in self.chat_to_stream:
                    if self.chat_to_stream[state.chat_id] == stream_id:
                        del self.chat_to_stream[state.chat_id]
                del self.streams[stream_id]
                print(f"[StreamManager] Removed stream {stream_id}")
    
    async def get_active_streams_for_user(self, user_id: int) -> list:
        """Get all active streams for a user"""
        async with self.lock:
            active_streams = []
            for stream_id, state in self.streams.items():
                if state.user_id == user_id and not state.is_complete:
                    active_streams.append({
                        "stream_id": stream_id,
                        "chat_id": state.chat_id,
                        "start_time": state.start_time,
                        "content_length": len(state.accumulated_content)
                    })
            return active_streams


# Global stream manager instance
stream_manager = StreamManager()

