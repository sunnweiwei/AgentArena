"""
Chat Client for interacting with the chat backend as a specific user.

Requirements:
    pip install requests websocket-client

Usage:
    with chat("weiwei", password="weiwei") as session:
        for chunk in session.send("Hello, how are you?"):
            print(chunk, end='', flush=True)
        
        # Get share link
        link = session.get_share_link()
        print(f"Share: {link}")
        
        # Stop generation if needed
        session.stop_generation()
"""

import requests
import websocket  # Package: websocket-client, Import: websocket
from websocket import WebSocketConnectionClosedException
import json
import threading
import queue
import time
from contextlib import contextmanager
from typing import Iterator, Optional, Dict, Any


class ChatSession:
    """A chat session for a specific user."""
    
    def __init__(self, username: str, password: str = "", 
                 backend_url: str = "http://sf.lti.cs.cmu.edu:8000",
                 ws_url: str = "ws://sf.lti.cs.cmu.edu:8000"):
        self.username = username
        self.password = password
        self.backend_url = backend_url.rstrip('/')
        self.ws_url = ws_url.rstrip('/')
        self.user_info: Optional[Dict[str, Any]] = None
        self.chat_id: Optional[str] = None
        self.ws: Optional[websocket.WebSocket] = None
        self.message_queue: queue.Queue = queue.Queue()
        self.ws_thread: Optional[threading.Thread] = None
        self.streaming = False
        self.current_stream_id: Optional[str] = None
        self._ws_closed = False
        
    def login(self) -> bool:
        """Login as the specified user."""
        try:
            response = requests.post(
                f"{self.backend_url}/api/auth/login",
                json={"email": self.username, "password": self.password or None}
            )
            response.raise_for_status()
            self.user_info = response.json()
            print(f"✓ Logged in as {self.username} (id: {self.user_info['user_id']})")
            return True
        except Exception as e:
            print(f"✗ Login failed: {e}")
            return False
    
    def create_chat(self) -> bool:
        """Create a new chat."""
        if not self.user_info:
            print("✗ Not logged in")
            return False
        
        try:
            response = requests.post(
                f"{self.backend_url}/api/chats",
                params={"user_id": self.user_info['user_id']}
            )
            response.raise_for_status()
            data = response.json()
            self.chat_id = data['id']
            print(f"✓ Created chat {self.chat_id}")
            return True
        except Exception as e:
            print(f"✗ Failed to create chat: {e}")
            return False
    
    def connect_websocket(self) -> bool:
        """Connect to WebSocket for streaming."""
        if not self.user_info or not self.chat_id:
            print("✗ No chat session")
            return False
        
        try:
            # Reset closed flag
            self._ws_closed = False
            
            # WebSocket endpoint expects user_id in the path
            ws_endpoint = f"{self.ws_url}/ws/{self.user_info['user_id']}"
            self.ws = websocket.WebSocket()
            self.ws.connect(ws_endpoint)
            
            # Start WebSocket listener thread
            self.ws_thread = threading.Thread(target=self._ws_listener, daemon=True)
            self.ws_thread.start()
            
            # Subscribe to the chat
            subscribe_msg = json.dumps({
                "type": "subscribe",
                "chat_id": self.chat_id
            })
            self.ws.send(subscribe_msg)
            
            print(f"✓ Connected to WebSocket")
            return True
        except Exception as e:
            print(f"✗ WebSocket connection failed: {e}")
            return False
    
    def _ws_listener(self):
        """Listen for WebSocket messages in a separate thread."""
        try:
            while not self._ws_closed and self.ws and self.ws.connected:
                try:
                    msg = self.ws.recv()
                    if msg:
                        data = json.loads(msg)
                        self.message_queue.put(data)
                except websocket.WebSocketTimeoutException:
                    continue
                except WebSocketConnectionClosedException:
                    # Connection closed normally
                    break
                except OSError as e:
                    # Handle "Bad file descriptor" and similar OS errors
                    if e.errno in (9, 32):  # Bad file descriptor or Broken pipe
                        break
                    print(f"WebSocket OS error: {e}")
                    break
                except Exception as e:
                    if not self._ws_closed:
                        print(f"WebSocket error: {e}")
                    break
        except Exception as e:
            if not self._ws_closed and "Bad file descriptor" not in str(e):
                print(f"WebSocket listener error: {e}")
    
    def send(self, message: str, chat_type: str = "normal") -> Iterator[str]:
        """
        Send a message and yield streaming chunks.
        
        Args:
            message: The message to send
            chat_type: Type of chat ("normal", "repo", "bc", "tau")
            
        Yields:
            String chunks as they arrive
        """
        if not self.user_info or not self.chat_id:
            raise RuntimeError("No active chat session")
        
        if not self.ws or not self.ws.connected:
            self.connect_websocket()
        
        try:
            # Clear the queue
            while not self.message_queue.empty():
                try:
                    self.message_queue.get_nowait()
                except queue.Empty:
                    break
            
            # Send the message via WebSocket
            ws_message = json.dumps({
                "type": "message",
                "chat_id": self.chat_id,
                "content": message,
                "model": "Auto",
                "meta_info": chat_type  # Use chat_type as meta_info (repo, bc, tau, etc.)
            })
            self.ws.send(ws_message)
            
            # Yield chunks as they come in
            self.streaming = True
            complete = False
            timeout_counter = 0
            max_timeout = 600  # 60 seconds (100ms * 600) - longer for repo/bc tasks
            
            while not complete and timeout_counter < max_timeout:
                try:
                    data = self.message_queue.get(timeout=0.1)
                    timeout_counter = 0  # Reset timeout on message
                    
                    msg_type = data.get('type')
                    
                    if msg_type == 'message_start':
                        # Capture stream_id for later cancellation
                        self.current_stream_id = data.get('stream_id')
                    
                    elif msg_type == 'message_chunk':
                        # Backend sends 'message_chunk', not 'chunk'
                        chunk_text = data.get('content', '')
                        if chunk_text:
                            yield chunk_text
                    
                    elif msg_type == 'message_complete':
                        self.current_stream_id = None  # Clear stream_id
                        complete = True
                        break
                    
                    elif msg_type == 'error':
                        self.current_stream_id = None  # Clear stream_id
                        error_msg = data.get('error', 'Unknown error')
                        raise RuntimeError(f"Stream error: {error_msg}")
                    
                    # Ignore other message types (meta_info_update, message, etc.)
                    
                except queue.Empty:
                    timeout_counter += 1
                    continue
            
            self.streaming = False
            
            if timeout_counter >= max_timeout:
                print("\n⚠ Stream timeout")
            
        except Exception as e:
            self.streaming = False
            raise RuntimeError(f"Failed to send message: {e}")
    
    def get_messages(self) -> list:
        """Get all messages in the current chat."""
        if not self.chat_id:
            return []
        
        try:
            response = requests.get(
                f"{self.backend_url}/api/chats/{self.chat_id}",
                params={"user_id": self.user_info['user_id']}
            )
            response.raise_for_status()
            data = response.json()
            return data.get('messages', [])
        except Exception as e:
            print(f"✗ Failed to get messages: {e}")
            return []
    
    def get_share_link(self) -> Optional[str]:
        """
        Get the share link for the current chat.
        
        Returns:
            Share URL string, or None if failed
            
        Example:
            >>> with chat("weiwei") as session:
            >>>     session.send("Hello")
            >>>     link = session.get_share_link()
            >>>     print(f"Share: {link}")
        """
        if not self.chat_id or not self.user_info:
            print("✗ No active chat")
            return None
        
        try:
            response = requests.post(
                f"{self.backend_url}/api/chats/{self.chat_id}/share",
                params={"user_id": self.user_info['user_id']}
            )
            response.raise_for_status()
            data = response.json()
            
            # Get the frontend URL from backend URL
            # Replace port 8000 with 3000 for frontend
            frontend_url = self.backend_url.replace(':8000', ':3000')
            share_token = data.get('share_token')
            
            if share_token:
                share_url = f"{frontend_url}/chat?share={share_token}"
                print(f"✓ Share link: {share_url}")
                return share_url
            else:
                print("✗ No share token received")
                return None
                
        except Exception as e:
            print(f"✗ Failed to get share link: {e}")
            return None
    
    def stop_generation(self):
        """Stop the current generation/stream."""
        if not self.ws or not (self.current_stream_id or self.chat_id):
            print("✗ No active stream to stop")
            return False
        
        try:
            stop_msg = {
                "type": "stop"
            }
            
            # Prefer stream_id for more precise cancellation
            if self.current_stream_id:
                stop_msg["stream_id"] = self.current_stream_id
                print(f"✓ Stopping stream {self.current_stream_id}")
            elif self.chat_id:
                stop_msg["chat_id"] = self.chat_id
                print(f"✓ Stopping chat {self.chat_id}")
            
            self.ws.send(json.dumps(stop_msg))
            self.streaming = False
            self.current_stream_id = None
            return True
        except Exception as e:
            print(f"✗ Failed to stop generation: {e}")
            return False
    
    def close(self):
        """Close the session and stop any active streams."""
        self.streaming = False
        
        # Send stop signal to cancel any active streams
        if self.ws and not self._ws_closed and (self.current_stream_id or self.chat_id):
            try:
                stop_msg = {
                    "type": "stop"
                }
                
                # Prefer stream_id for more precise cancellation
                if self.current_stream_id:
                    stop_msg["stream_id"] = self.current_stream_id
                    print(f"✓ Sending stop signal for stream {self.current_stream_id}")
                elif self.chat_id:
                    stop_msg["chat_id"] = self.chat_id
                    print(f"✓ Sending stop signal for chat {self.chat_id}")
                
                self.ws.send(json.dumps(stop_msg))
                time.sleep(0.1)  # Brief delay to ensure message is sent
            except Exception as e:
                if not self._ws_closed:
                    print(f"⚠ Failed to send stop signal: {e}")
        
        # Set flag to stop listener thread
        self._ws_closed = True
        
        # Close WebSocket connection
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                pass  # Ignore errors when closing
            self.ws = None
        
        # Wait for listener thread to finish (with timeout)
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=1.0)
        
        print(f"✓ Session closed")


@contextmanager
def chat(username: str, password: str = "", 
         backend_url: str = "http://sf.lti.cs.cmu.edu:8000",
         ws_url: str = "ws://sf.lti.cs.cmu.edu:8000"):
    """
    Context manager for creating a chat session.
    
    Args:
        username: Username to login as
        password: Password (optional)
        backend_url: HTTP backend URL
        ws_url: WebSocket backend URL
    
    Usage:
        with chat("weiwei") as session:
            for chunk in session.send("Hello!"):
                print(chunk, end='', flush=True)
    """
    session = ChatSession(username, password, backend_url, ws_url)
    
    try:
        if not session.login():
            raise RuntimeError(f"Failed to login as {username}")
        
        if not session.create_chat():
            raise RuntimeError("Failed to create chat")
        
        if not session.connect_websocket():
            raise RuntimeError("Failed to connect WebSocket")
        
        yield session
    
    finally:
        session.close()


# Example usage
if __name__ == "__main__":
    # Example 1: Simple usage
    print("\n" + "=" * 50)
    print("Example 4: Repo chat")
    print("=" * 50)
    
    with chat("weiwei", "weiwei") as session:
        print("\nSending repo message...")
        for chunk in session.send(
            "\\repo instance_id:astropy__astropy-13033",
            chat_type="repo"
        ):
            print(chunk, end='', flush=True)
        print()
