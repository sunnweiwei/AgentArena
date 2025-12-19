from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uuid
import asyncio
import os
import time
import tempfile
import secrets
from openai import OpenAI
import aiohttp
import json

# Database setup with connection pooling
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat_data.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,
    max_overflow=40,
    pool_timeout=30,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    chats = relationship("Chat", back_populates="user")

class Chat(Base):
    __tablename__ = "chats"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    meta_info = Column(Text, default="")  # Meta information for agent context
    share_token = Column(String, unique=True, index=True, nullable=True)  # Token for sharing chat (nullable for existing chats)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", order_by="Message.created_at")
    # Note: For existing databases, SQLite will automatically add the nullable share_token column
    # when the table schema is updated. No manual migration needed.

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chats.id"))
    role = Column(String)  # "user" or "assistant"
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")

# Create tables
Base.metadata.create_all(bind=engine)

# Load OpenAI API key
OPENAI_API_KEY = None
try:
    # Try relative to backend directory first
    key_path = os.path.join(os.path.dirname(__file__), '..', 'openaikey')
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            OPENAI_API_KEY = f.read().strip()
    else:
        # Try absolute path
        with open('/usr1/data/weiweis/chat_server/openaikey', 'r') as f:
            OPENAI_API_KEY = f.read().strip()
except Exception as e:
    print(f"Warning: Could not load OpenAI API key: {e}")

# Initialize OpenAI client
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print(f"OpenAI client initialized successfully")
else:
    print(f"Warning: OpenAI API key not loaded, OpenAI features disabled")

TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-transcribe")

# Model mapping
MODEL_MAP = {
    "Auto": "search_agent",  # Default to Search Agent
    "GPT-5-Nano": "gpt-5-nano",
    "GPT-5-Mini": "gpt-5-mini",
    "Search Agent": "search_agent"
}

# External API configuration for models
EXTERNAL_MODEL_APIS = {
    "search_agent": os.getenv("SEARCH_AGENT_URL", "http://sf.lti.cs.cmu.edu:8001")
}


def _event_to_dict(event):
    """Best-effort conversion of OpenAI stream events to plain dicts."""
    if isinstance(event, dict):
        return event
    for attr in ("model_dump", "to_dict_recursive", "to_dict"):
        fn = getattr(event, attr, None)
        if callable(fn):
            try:
                return fn()
            except TypeError:
                try:
                    return fn(mode="python")
                except TypeError:
                    continue
    return None


def _normalize_text_delta(delta):
    """Extract plain text from diverse delta payload formats."""
    if not delta:
        return ""
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        for key in ("text", "content", "delta"):
            value = delta.get(key)
            if isinstance(value, str):
                return value
        return ""
    if isinstance(delta, list):
        parts = []
        for item in delta:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if "text" in item and isinstance(item["text"], str):
                    parts.append(item["text"])
                elif "content" in item and isinstance(item["content"], str):
                    parts.append(item["content"])
        return "".join(parts)
    return str(delta)


def _extract_text_from_response_event(event):
    """Pull streaming text from an OpenAI Responses event."""
    delta = getattr(event, "delta", None)
    if delta:
        return _normalize_text_delta(delta)
    event_dict = _event_to_dict(event)
    if not event_dict:
        return ""
    delta = event_dict.get("delta") or event_dict.get("output")
    return _normalize_text_delta(delta)


def _extract_error_from_response_event(event):
    """Return a readable error message from an OpenAI Responses event."""
    message = getattr(event, "message", None)
    if isinstance(message, str) and message:
        return message
    event_dict = _event_to_dict(event)
    if not event_dict:
        return None
    error = event_dict.get("error")
    if isinstance(error, dict):
        return error.get("message") or error.get("code")
    if isinstance(error, str):
        return error
    return event_dict.get("message")

# FastAPI app
app = FastAPI()

# CORS middleware
# Allow all origins for cloud hosting (frontend may be on different server)
# Can be restricted by setting ALLOWED_ORIGINS env var (comma-separated list)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
if allowed_origins_env:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    allow_credentials = True
else:
    # Default: allow common origins + all origins for cloud hosting
    # Note: Using "*" requires allow_credentials=False, so we allow all with regex
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://sf.lti.cs.cmu.edu:3000",
        "https://sf.lti.cs.cmu.edu:3443",
        "http://sf.lti.cs.cmu.edu",
        "https://sf.lti.cs.cmu.edu",
        "http://localhost:4173"
    ]
    # For cloud hosting: allow all origins (frontend on different server)
    # Set ALLOWED_ORIGINS env var to restrict to specific origins if needed
    allow_credentials = False  # Required when allowing all origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins_env else ["*"],
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test streaming endpoint
@app.websocket("/ws/test-stream")
async def test_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Test stream client connected")
    
    try:
        # Wait for start message
        data = await websocket.receive_json()
        if data.get("type") == "start_test":
            print("Starting test stream with OpenAI...")
            
            if openai_client:
                # Use real OpenAI API
                try:
                    stream = openai_client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": "user", "content": "Write a 100-word document about artificial intelligence."}
                        ],
                        stream=True
                    )
                    
                    for chunk in stream:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta.content:
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": delta.content
                                })
                                print(f"Sent chunk: {delta.content!r}")
                    
                    # Send completion
                    await websocket.send_json({
                        "type": "complete"
                    })
                    print("Test stream complete")
                    
                except Exception as openai_err:
                    print(f"OpenAI error in test: {openai_err}")
                    await websocket.send_json({
                        "type": "error",
                        "content": str(openai_err)
                    })
            else:
                # Fallback to fake data
                print("OpenAI not available, using fake data")
                words = ["Hello", "this", "is", "a", "streaming", "test", "where", "each", "word", "arrives", "every", "0.1", "seconds"]
                
                for word in words:
                    await asyncio.sleep(0.1)
                    await websocket.send_json({
                        "type": "chunk",
                        "content": word + " "
                    })
                    print(f"Sent word: {word}")
                
                await websocket.send_json({
                    "type": "complete"
                })
            
    except Exception as e:
        print(f"Test stream error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await websocket.close()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: dict = {}  # user_id -> set of WebSockets
        self.connection_locks: dict = {}  # WebSocket -> asyncio.Lock
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_connections.setdefault(user_id, set()).add(websocket)
        self.connection_locks[websocket] = asyncio.Lock()
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        connections = self.user_connections.get(user_id)
        if connections and websocket in connections:
            connections.remove(websocket)
            if not connections:
                del self.user_connections[user_id]
        if websocket in self.connection_locks:
            del self.connection_locks[websocket]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        lock = self.connection_locks.get(websocket)
        if lock is None:
            await websocket.send_json(message)
            return
        async with lock:
            await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            lock = self.connection_locks.get(connection)
            if lock is None:
                continue
            async with lock:
                await connection.send_json(message)

manager = ConnectionManager()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper function to get or create user
def get_or_create_user(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# API Routes
class LoginRequest(BaseModel):
    email: str

@app.post("/api/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Simple username-based login (any string)"""
    try:
        username = request.email.strip()  # Reusing email field for username
        if not username:
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        
        user = get_or_create_user(db, username)
        return {
            "user_id": user.id,
            "email": user.email,  # Still called email in response for compatibility
            "message": "Login successful"
        }
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/api/chats")
async def get_user_chats(user_id: int, db: Session = Depends(get_db)):
    """Get all chats for a user (only chats with messages), sorted by last user message time"""
    chats = db.query(Chat).filter(Chat.user_id == user_id).all()
    # Filter out empty chats and sort by last user message time
    chats_with_messages = [chat for chat in chats if len(chat.messages) > 0]
    
    # Sort by last user message time (most recent first)
    def get_last_user_message_time(chat):
        user_messages = [msg for msg in chat.messages if msg.role == "user"]
        if user_messages:
            return max(msg.created_at for msg in user_messages)
        # Fallback to updated_at if no user messages (shouldn't happen)
        return chat.updated_at
    
    chats_with_messages.sort(key=get_last_user_message_time, reverse=True)
    
    return [
        {
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat(),
            "message_count": len(chat.messages),
            "last_user_message_time": max(
                (msg.created_at for msg in chat.messages if msg.role == "user"),
                default=chat.updated_at
            ).isoformat()
        }
        for chat in chats_with_messages
    ]

@app.post("/api/chats")
async def create_chat(user_id: int, db: Session = Depends(get_db)):
    """Create a new chat"""
    chat_id = str(uuid.uuid4())
    chat = Chat(id=chat_id, user_id=user_id, title="New Chat")
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return {
        "id": chat.id,
        "title": chat.title,
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat()
    }

@app.get("/api/chats/{chat_id}")
async def get_chat(chat_id: str, user_id: int, db: Session = Depends(get_db)):
    """Get chat with all messages"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    return {
        "id": chat.id,
        "title": chat.title,
        "meta_info": chat.meta_info or "",
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in chat.messages
        ]
    }

@app.put("/api/chats/{chat_id}/title")
async def update_chat_title(chat_id: str, title: str, user_id: int, db: Session = Depends(get_db)):
    """Update chat title"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    chat.title = title
    chat.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Title updated"}

@app.post("/api/chats/{chat_id}/share")
async def share_chat(chat_id: str, user_id: int, request: Request, db: Session = Depends(get_db)):
    """Generate a share token for a chat"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Generate a unique share token if not exists
    if not chat.share_token:
        # Generate a secure random token
        chat.share_token = secrets.token_urlsafe(32)
        db.commit()
    
    # Get base URL from request
    scheme = request.url.scheme
    host = request.headers.get("host", "localhost:5173")
    # Try to get origin from headers (set by frontend proxy)
    origin = request.headers.get("origin") or request.headers.get("referer")
    if origin:
        base_url = origin.rstrip('/')
    else:
        base_url = f"{scheme}://{host}"
    
    share_url = f"{base_url}?share={chat.share_token}"
    
    return {
        "share_token": chat.share_token,
        "share_url": share_url
    }

@app.get("/api/shared/{share_token}")
async def get_shared_chat(share_token: str, db: Session = Depends(get_db)):
    """Get a shared chat by share token (public endpoint, no auth required)"""
    chat = db.query(Chat).filter(Chat.share_token == share_token).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Shared chat not found")
    
    return {
        "id": chat.id,
        "title": chat.title,
        "meta_info": chat.meta_info or "",
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat()
            }
            for msg in chat.messages
        ]
    }

@app.post("/api/chats/{chat_id}/messages")
async def add_message(chat_id: str, content: str, role: str, user_id: int, db: Session = Depends(get_db)):
    """Add a message to a chat"""
    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    message = Message(chat_id=chat_id, role=role, content=content)
    db.add(message)
    
    # Update chat title if it's the first user message
    if role == "user" and len(chat.messages) == 0:
        # Use first 50 chars of message as title
        chat.title = content[:50] + ("..." if len(content) > 50 else "")
    
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)
    
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat()
    }

# Audio transcription endpoint
@app.post("/api/audio/transcribe")
async def transcribe_audio(file: UploadFile = File(...), model: Optional[str] = None):
    """Transcribe audio file to text using OpenAI Whisper API"""
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI client not available")
    
    # Validate file type - check both content_type and filename extension
    allowed_types = ["audio/mpeg", "audio/mp3", "audio/mp4", "audio/mpeg", "audio/mpga", "audio/m4a", "audio/wav", "audio/webm"]
    allowed_extensions = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]
    
    file_extension = ""
    if file.filename:
        file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file.content_type not in allowed_types and file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Content-Type: {file.content_type}, Extension: {file_extension}. Supported: {allowed_types}"
        )
    
    try:
        # Read file content
        contents = await file.read()
        
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
        
        # Determine file extension for temp file
        ext = file_extension if file_extension else ".webm"  # Default to webm for browser recordings
        if not ext.startswith("."):
            ext = ".webm"
        
        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_file.write(contents)
            tmp_file_path = tmp_file.name
        
        try:
            # Log file info for debugging
            file_size = os.path.getsize(tmp_file_path)
            print(f"[Transcribe] Processing audio file: {tmp_file_path}, size: {file_size} bytes, type: {file.content_type}, ext: {ext}")
            
            # Transcribe using OpenAI - use gpt-4o-transcribe for best accuracy
            print(f"[Transcribe] Using model: {TRANSCRIPTION_MODEL}")
            with open(tmp_file_path, "rb") as audio_file:
                transcription = openai_client.audio.transcriptions.create(
                    model=TRANSCRIPTION_MODEL,
                    file=audio_file,
                    response_format="text"
                )
            
            # Handle both string and object responses
            text = transcription if isinstance(transcription, str) else transcription.text
            print(f"[Transcribe] Transcription result: {text[:100]}... (length: {len(text)})")
            return {"text": text}
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception as cleanup_err:
                    print(f"Warning: Failed to delete temp file {tmp_file_path}: {cleanup_err}")
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Transcription error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}

# WebSocket endpoint for real-time chat with multiplexed streams
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    active_tasks = set()
    active_streams = {}  # stream_id -> task mapping for cancellation
    cancelled_streams = set()  # Track cancelled stream_ids
    try:
        try:
            resolved_user_id = int(user_id)
        except (TypeError, ValueError):
            await websocket.close(code=1008)
            return

        print(f"[WS] Incoming connection for user {resolved_user_id}")
        await manager.connect(websocket, resolved_user_id)
        print(f"[WS] Connection accepted for user {resolved_user_id}")

        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "message":
                    chat_id = data.get("chat_id")
                    content = data.get("content", "").strip()
                    model = data.get("model", "Auto")
                    meta_info = data.get("meta_info", "")

                    if not chat_id:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "chat_id is required"
                        }, websocket)
                        continue

                    if not content:
                        continue

                    # Generate stream_id upfront for tracking
                    stream_id = f"stream-{chat_id}-{int(asyncio.get_event_loop().time() * 1000)}"
                    
                    task = asyncio.create_task(handle_chat_message(
                        websocket=websocket,
                        user_id=resolved_user_id,
                        chat_id=chat_id,
                        content=content,
                        model=model,
                        meta_info=meta_info,
                        stream_id=stream_id,
                        cancelled_streams=cancelled_streams
                    ))
                    active_tasks.add(task)
                    active_streams[stream_id] = task
                    
                    def cleanup_task(t, sid=stream_id):
                        active_tasks.discard(t)
                        active_streams.pop(sid, None)
                    
                    task.add_done_callback(cleanup_task)

                elif msg_type == "stop":
                    # Handle stop generation request
                    stream_id_to_stop = data.get("stream_id")
                    chat_id_to_stop = data.get("chat_id")
                    
                    print(f"[WS] Stop request received. stream_id={stream_id_to_stop}, chat_id={chat_id_to_stop}")
                    
                    # Add to cancelled set
                    if stream_id_to_stop:
                        cancelled_streams.add(stream_id_to_stop)
                    
                    # Find and cancel the task
                    task_to_cancel = None
                    if stream_id_to_stop and stream_id_to_stop in active_streams:
                        task_to_cancel = active_streams.get(stream_id_to_stop)
                    elif chat_id_to_stop:
                        # Try to find by chat_id prefix
                        for sid, task in list(active_streams.items()):
                            if sid.startswith(f"stream-{chat_id_to_stop}-"):
                                task_to_cancel = task
                                cancelled_streams.add(sid)
                                break
                    
                    if task_to_cancel and not task_to_cancel.done():
                        print(f"[WS] Cancelling task for stream")
                        task_to_cancel.cancel()
                    else:
                        print(f"[WS] No active task found to cancel")

                elif msg_type == "ping":
                    try:
                        await manager.send_personal_message({"type": "pong"}, websocket)
                    except Exception as ping_err:
                        print(f"Error sending pong: {ping_err}")

            except WebSocketDisconnect:
                break
            except Exception as loop_err:
                print(f"Error in WebSocket loop: {loop_err}")
                import traceback
                traceback.print_exc()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        for task in active_tasks:
            task.cancel()
        try:
            manager.disconnect(websocket, resolved_user_id)
        except Exception:
            pass


async def call_external_model_api(api_url: str, messages_history: list, websocket: WebSocket, chat_id: str, user_id: int, stream_id: str, meta_info: str = "", cancelled_streams: set = None):
    """
    Generic function to call any external model API with OpenAI-compatible streaming.
    Handles streaming response from external API servers.
    
    Args:
        api_url: Base URL of the external API server
        messages_history: Conversation history
        websocket: WebSocket connection to client
        chat_id: Chat identifier
        user_id: User identifier
        stream_id: Stream identifier
        meta_info: Meta information for agent context
        cancelled_streams: Set of cancelled stream IDs
    """
    full_response = ""
    chunk_index = 0
    cancelled_streams = cancelled_streams or set()
    was_cancelled = False
    
    try:
        # Prepare request (OpenAI-compatible format)
        request_payload = {
            "messages": messages_history,
            "stream": True,
            "meta_info": meta_info
        }
        
        # Call external API with streaming
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/v1/chat/completions",
                json=request_payload,
                timeout=aiohttp.ClientTimeout(total=7200)  # 2 hour timeout for long agent tasks
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"External API error: {response.status} - {error_text}")
                
                # Process streaming response (SSE format) - read line by line
                buffer = b""
                async for chunk in response.content.iter_any():
                    # Check for cancellation
                    if stream_id in cancelled_streams:
                        print(f"[External API] Stream {stream_id} cancelled by user")
                        was_cancelled = True
                        break
                    
                    buffer += chunk
                    
                    # Process complete lines
                    while b'\n' in buffer:
                        line_bytes, buffer = buffer.split(b'\n', 1)
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or line.startswith(':'):
                            continue
                        
                        if line.startswith('info: '):
                            # Handle meta info update
                            info_str = line[6:]  # Remove 'info: ' prefix
                            try:
                                info_content = info_str
                                
                                if info_content:
                                    print(f"[External API] Info update: {info_content[:100]}...")
                                    
                                    # Update meta_info in database
                                    with SessionLocal() as db:
                                        chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                                        if chat:
                                            current_meta = chat.meta_info or ""
                                            if len(current_meta) != 0:
                                                chat.meta_info = current_meta + "\n\n" + info_content
                                            else:
                                                chat.meta_info = current_meta + info_content
                                            db.commit()
                                    
                                    # Send info update to client
                                    await manager.send_personal_message({
                                        "type": "meta_info_update",
                                        "content": info_content,
                                        "stream_id": stream_id,
                                        "chat_id": chat_id
                                    }, websocket)
                            
                            except json.JSONDecodeError:
                                print(f"Failed to parse info JSON: {info_str}")
                            continue
                        
                        if line.startswith('data: '):
                            data_str = line[6:]  # Remove 'data: ' prefix
                            
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                
                                # Check for errors
                                if 'error' in chunk_data:
                                    raise RuntimeError(f"API error: {chunk_data['error'].get('message', 'Unknown error')}")
                                
                                # Extract content from OpenAI-like format
                                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        print(f"[External API] Chunk {chunk_index + 1}: {len(content)} chars")
                                        full_response += content
                                        
                                        # Send chunk to client immediately
                                        chunk_index += 1
                                        await manager.send_personal_message({
                                            "type": "message_chunk",
                                            "content": content,
                                            "stream_id": stream_id,
                                            "chunk_index": chunk_index,
                                            "chat_id": chat_id
                                        }, websocket)
                                    
                                    # Check for finish_reason
                                    finish_reason = chunk_data['choices'][0].get('finish_reason')
                                    if finish_reason == 'stop':
                                        break
                            
                            except json.JSONDecodeError:
                                print(f"Failed to parse JSON: {data_str}")
                                continue
        
        # Prepare the final content
        final_content = full_response
        
        # Save complete/partial message to database
        with SessionLocal() as db:
            chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
            if not chat:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Chat not found",
                    "chat_id": chat_id
                }, websocket)
                return full_response
            
            message = Message(chat_id=chat_id, role="assistant", content=final_content)
            db.add(message)
            chat.updated_at = datetime.utcnow()
            db.commit()
            
            # Send message complete with ID
            status = "cancelled" if was_cancelled else "completed"
            print(f"[External API] Response {status} for chat {chat_id} (stream {stream_id})")
            await manager.send_personal_message({
                "type": "message_complete",
                "id": message.id,
                "role": "assistant",
                "content": final_content,
                "created_at": message.created_at.isoformat(),
                "stream_id": stream_id,
                "chunk_count": chunk_index,
                "chat_id": chat_id
            }, websocket)
        
        return full_response
        
    except asyncio.CancelledError:
        # Handle cancellation gracefully - save partial response
        print(f"[External API] Task cancelled for stream {stream_id}")
        final_content = full_response
        if full_response.strip():
            try:
                with SessionLocal() as db:
                    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                    if chat:
                        message = Message(chat_id=chat_id, role="assistant", content=final_content)
                        db.add(message)
                        chat.updated_at = datetime.utcnow()
                        db.commit()
                        
                        await manager.send_personal_message({
                            "type": "message_complete",
                            "id": message.id,
                            "role": "assistant",
                            "content": final_content,
                            "created_at": message.created_at.isoformat(),
                            "stream_id": stream_id,
                            "chat_id": chat_id
                        }, websocket)
            except Exception as save_err:
                print(f"Error saving cancelled response: {save_err}")
        else:
            # No content - just send message_complete to close
            try:
                await manager.send_personal_message({
                    "type": "message_complete",
                    "id": None,
                    "role": "assistant",
                    "content": "*Generation stopped by user*",
                    "created_at": datetime.utcnow().isoformat(),
                    "stream_id": stream_id,
                    "chat_id": chat_id
                }, websocket)
            except Exception:
                pass
        return full_response
        
    except Exception as e:
        import traceback

        # Log rich diagnostics about the external error
        print(f"External API error: {e!r}")
        print(f"External API error type: {type(e).__name__}")
        traceback.print_exc()

        error_msg = str(e) or type(e).__name__

        # If we already have some content, preserve it and treat the error as partial failure
        if full_response.strip():
            # Append a short note to the end of the model output so the user
            # sees the incomplete answer first, then the error notice.
            short_msg = error_msg
            if len(short_msg) > 300:
                short_msg = short_msg[:300] + "..."
            
            response_with_note = (
                full_response
                + f"\n\n---\n⚠️ **Response incomplete**: {short_msg}"
            )
            try:
                # Save the message to database FIRST, then send with proper ID
                with SessionLocal() as db:
                    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                    if chat:
                        message = Message(
                            chat_id=chat_id,
                            role="assistant",
                            content=response_with_note,
                            created_at=datetime.utcnow()
                        )
                        db.add(message)
                        chat.updated_at = datetime.utcnow()
                        db.commit()
                        db.refresh(message)
                        
                        await manager.send_personal_message({
                            "type": "message_complete",
                            "id": message.id,
                            "role": "assistant",
                            "content": response_with_note,
                            "created_at": message.created_at.isoformat(),
                            "stream_id": stream_id,
                            "chat_id": chat_id
                        }, websocket)
            except Exception as send_err:
                print(f"Error saving/sending partial external response: {send_err}")
            return full_response

        # No content at all – behave like a hard failure
        await manager.send_personal_message({
            "type": "error",
            "message": f"API error: {error_msg}",
            "stream_id": stream_id,
            "chat_id": chat_id
        }, websocket)
        return ""


async def handle_chat_message(websocket: WebSocket, user_id: int, chat_id: str, content: str, model: str, meta_info: str = "", stream_id: str = None, cancelled_streams: set = None):
    user_payload = None
    stream_id = stream_id or str(uuid.uuid4())
    cancelled_streams = cancelled_streams or set()

    try:
        with SessionLocal() as db:
            chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
            if not chat:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Chat not found",
                    "chat_id": chat_id
                }, websocket)
                return

            user_message = Message(chat_id=chat_id, role="user", content=content)
            db.add(user_message)

            if len(chat.messages) == 0:
                chat.title = content[:50] + ("..." if len(content) > 50 else "")

            chat.updated_at = datetime.utcnow()
            db.commit()
            user_payload = {
                "type": "message",
                "id": user_message.id,
                "role": "user",
                "content": content,
                "created_at": user_message.created_at.isoformat(),
                "chat_id": chat_id
            }

    except Exception as db_err:
        print(f"Database error saving user message: {db_err}")
        try:
            await manager.send_personal_message({
                "type": "error",
                "message": "Failed to save message",
                "chat_id": chat_id
            }, websocket)
        except Exception:
            pass
        return

    # Send user message acknowledgement
    if user_payload:
        try:
            await manager.send_personal_message(user_payload, websocket)
        except Exception as send_err:
            print(f"Error sending user message: {send_err}")

    # Handle agent response
    try:
        print(f"Received model: {model}, OpenAI client available: {openai_client is not None}")
        openai_model = MODEL_MAP.get(model)
        print(f"Mapped model: {openai_model}")
        
        # Check if model uses external API
        if openai_model and openai_model in EXTERNAL_MODEL_APIS:
            # Use external API
            external_api_url = EXTERNAL_MODEL_APIS[openai_model]
            
            # Get conversation history
            with SessionLocal() as db:
                chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                if not chat:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Chat not found",
                        "chat_id": chat_id
                    }, websocket)
                    return
                
                # Build message history (user message already in chat.messages after commit)
                messages_history = []
                for msg in chat.messages:
                    messages_history.append({"role": msg.role, "content": msg.content})
            
            # Start streaming response
            start_time = time.time()
            print(f"[TIMING] External API streaming started for chat {chat_id} (stream {stream_id}) at {start_time}")
            await manager.send_personal_message({
                "type": "message_start",
                "role": "assistant",
                "stream_id": stream_id,
                "chat_id": chat_id
            }, websocket)
            
            # Get meta_info from chat
            chat_meta_info = chat.meta_info or ""
            
            # Stream response from external API
            await call_external_model_api(external_api_url, messages_history, websocket, chat_id, user_id, stream_id, chat_meta_info, cancelled_streams)
            
        elif openai_model is None or openai_client is None:
            # Use simulated response for Auto or if OpenAI not available
            await asyncio.sleep(0.5)
            agent_response = f"This is a simulated agent response to: {content[:30]}..."

            with SessionLocal() as db:
                chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                if not chat:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Chat not found",
                        "chat_id": chat_id
                    }, websocket)
                    return

                agent_message = Message(chat_id=chat_id, role="assistant", content=agent_response)
                db.add(agent_message)
                chat.updated_at = datetime.utcnow()
                db.commit()
                
                await manager.send_personal_message({
                    "type": "message",
                    "id": agent_message.id,
                    "role": "assistant",
                    "content": agent_response,
                    "created_at": agent_message.created_at.isoformat(),
                    "chat_id": chat_id
                }, websocket)
        else:
            # Use OpenAI streaming
            # Get conversation history
            with SessionLocal() as db:
                chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                if not chat:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Chat not found",
                        "chat_id": chat_id
                    }, websocket)
                    return
                
                # Build message history with system prompt (user message already in chat.messages after commit)
                messages_history = [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Always respond in English. When creating tables, use proper Markdown table syntax (| Column | Column |) instead of ASCII art tables. Format your responses clearly with proper Markdown formatting."
                    }
                ]
                messages_history.extend([
                    {"role": msg.role, "content": msg.content}
                    for msg in chat.messages
                ])

            # Start streaming response (use provided stream_id)
            start_time = time.time()
            print(f"[TIMING] Streaming response started for chat {chat_id} (stream {stream_id}) at {start_time}")
            await manager.send_personal_message({
                "type": "message_start",
                "role": "assistant",
                "stream_id": stream_id,
                "chat_id": chat_id
            }, websocket)

            full_response = ""
            try:
                loop = asyncio.get_running_loop()
                stream_queue: asyncio.Queue = asyncio.Queue()

                def stream_worker():
                    try:
                        api_call_start = time.time()
                        print(f"[TIMING] Calling OpenAI API with model {openai_model}")
                        stream = openai_client.responses.create(
                            model=openai_model,
                            input=messages_history,
                            stream=True
                        )
                        api_call_time = time.time() - api_call_start
                        print(f"[TIMING] OpenAI API call returned in {api_call_time*1000:.2f}ms")
                        for ev in stream:
                            loop.call_soon_threadsafe(stream_queue.put_nowait, ("event", ev))
                        loop.call_soon_threadsafe(stream_queue.put_nowait, ("done", None))
                    except Exception as worker_err:
                        print(f"OpenAI worker error: {worker_err}")
                        loop.call_soon_threadsafe(stream_queue.put_nowait, ("error", worker_err))

                worker_task = asyncio.create_task(asyncio.to_thread(stream_worker))

                                # Batch chunks that arrive within 0.1s for smoother output
                batch_buffer = ""
                last_send_time = asyncio.get_event_loop().time()
                first_chunk_received = False
                streaming_error = None
                chunk_index = 0

                was_cancelled = False
                while True:
                    # Check for cancellation
                    if stream_id in cancelled_streams:
                        print(f"[OpenAI] Stream {stream_id} cancelled by user")
                        was_cancelled = True
                        worker_task.cancel()
                        break
                    
                    try:
                        # Use timeout to allow checking for cancellation periodically
                        event_type, payload = await asyncio.wait_for(stream_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue
                    
                    if event_type == "done":
                        break
                    if event_type == "error":
                        streaming_error = str(payload)
                        break
                    event = payload
                    event_type = getattr(event, "type", None)
                    if not first_chunk_received and event_type and "delta" in event_type:
                        first_chunk_time = time.time() - start_time
                        print(f"[TIMING] First chunk received after {first_chunk_time*1000:.2f}ms")
                        first_chunk_received = True

                    if isinstance(event_type, str) and "output_text" in event_type and "delta" in event_type:
                        delta_text = _extract_text_from_response_event(event)
                        if not delta_text:
                            continue
                        print(f"Streaming chunk: {delta_text!r}")
                        full_response += delta_text
                        batch_buffer += delta_text

                        current_time = asyncio.get_event_loop().time()
                        if (current_time - last_send_time >= 0.1) or len(batch_buffer) > 80:
                            chunk_index += 1
                            await manager.send_personal_message({
                                "type": "message_chunk",
                                "content": batch_buffer,
                                "stream_id": stream_id,
                                "chunk_index": chunk_index,
                                "chat_id": chat_id
                            }, websocket)
                            print(f"Sent batched chunk: {len(batch_buffer)} chars")
                            batch_buffer = ""
                            last_send_time = current_time

                    elif event_type in {"response.completed", "response.output_text.done"}:
                        print(f"Received completion event: {event_type}")
                        break

                    elif event_type in {"response.failed", "response.error", "error"}:
                        streaming_error = _extract_error_from_response_event(event) or "OpenAI streaming failed"
                        print(f"Streaming error event: {streaming_error}")
                        break

                    else:
                        # Other events (created, in-progress, etc.) are informational
                        continue

                # Send any remaining buffered content
                if batch_buffer:
                    chunk_index += 1
                    await manager.send_personal_message({
                        "type": "message_chunk",
                        "content": batch_buffer,
                        "stream_id": stream_id,
                        "chunk_index": chunk_index,
                        "chat_id": chat_id
                    }, websocket)
                    print(f"Sent final batched chunk: {len(batch_buffer)} chars")

                if streaming_error:
                    if not worker_task.done():
                        worker_task.cancel()
                    raise RuntimeError(streaming_error)

                if not worker_task.done():
                    try:
                        await worker_task
                    except asyncio.CancelledError:
                        pass

                # Prepare final content
                final_content = full_response

                # Save complete/partial message to database
                with SessionLocal() as db:
                    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                    if not chat:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "Chat not found",
                            "chat_id": chat_id
                        }, websocket)
                        return

                    agent_message = Message(chat_id=chat_id, role="assistant", content=final_content)
                    db.add(agent_message)
                    chat.updated_at = datetime.utcnow()
                    db.commit()

                    # Send message complete with ID
                    status = "cancelled" if was_cancelled else "completed"
                    print(f"Streaming response {status} for chat {chat_id} (stream {stream_id})")
                    await manager.send_personal_message({
                        "type": "message_complete",
                        "id": agent_message.id,
                        "role": "assistant",
                        "content": final_content,
                        "created_at": agent_message.created_at.isoformat(),
                        "stream_id": stream_id,
                        "chunk_count": chunk_index,
                        "chat_id": chat_id
                    }, websocket)

            except Exception as openai_err:
                import traceback
                print(f"OpenAI API error: {openai_err!r}")
                traceback.print_exc()
                error_msg = str(openai_err) or type(openai_err).__name__

                if full_response.strip():
                    # We have partial content: keep it and append a short note.
                    short_msg = error_msg
                    if len(short_msg) > 300:
                        short_msg = short_msg[:300] + "..."
                    response_with_note = (
                        full_response
                        + f"\n\n---\n⚠️ **Response incomplete**: {short_msg}"
                    )

                    # Persist partial response
                    with SessionLocal() as db:
                        chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                        if chat:
                            agent_message = Message(chat_id=chat_id, role="assistant", content=response_with_note)
                            db.add(agent_message)
                            chat.updated_at = datetime.utcnow()
                            db.commit()

                            # Tell client the stream is complete with the partial response
                            # DO NOT send error event - it causes frontend to delete the message!
                            await manager.send_personal_message({
                                "type": "message_complete",
                                "id": agent_message.id,
                                "role": "assistant",
                                "content": response_with_note,
                                "created_at": agent_message.created_at.isoformat(),
                                "stream_id": stream_id,
                                "chunk_count": chunk_index,
                                "chat_id": chat_id
                            }, websocket)
                else:
                    # No partial content at all – behave like a hard failure
                    await manager.send_personal_message({
                        "type": "error",
                        "message": f"Error calling OpenAI: {error_msg}",
                        "stream_id": stream_id,
                        "chat_id": chat_id
                    }, websocket)
                    # Also send message_complete to close the streaming message with an explicit error text
                    await manager.send_personal_message({
                        "type": "message_complete",
                        "id": None,
                        "role": "assistant",
                        "content": f"Error: {error_msg}",
                        "created_at": datetime.utcnow().isoformat(),
                        "chat_id": chat_id
                    }, websocket)

    except Exception as agent_err:
        import traceback
        print(f"Error generating agent response: {agent_err!r}")
        print(f"Agent error type: {type(agent_err).__name__}")
        traceback.print_exc()
        try:
            await manager.send_personal_message({
                "type": "error",
                "message": "Failed to generate response",
                "chat_id": chat_id
            }, websocket)
        except Exception:
            pass

@app.get("/")
async def root():
    return {"message": "Chat API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

