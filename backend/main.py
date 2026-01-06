from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict
import uuid
import asyncio
import os
import time
import tempfile
import secrets
from openai import OpenAI
import aiohttp
import json
from stream_manager import StreamManager, StreamState

stream_manager = StreamManager()

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
    password = Column(String, nullable=True)  # Optional password field
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
    survey_response = Column(Text, nullable=True)  # JSON string of survey responses
    chat = relationship("Chat", back_populates="messages")

class MCPServer(Base):
    __tablename__ = "mcp_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)  # User-friendly name
    server_id = Column(String, unique=True, index=True)  # Unique identifier
    command = Column(String)  # Command to run (e.g., "npx", "python")
    args = Column(Text)  # JSON array of arguments
    env = Column(Text, nullable=True)  # JSON object of environment variables
    enabled = Column(Integer, default=1)  # 1 = enabled, 0 = disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User")

class UserTool(Base):
    __tablename__ = "user_tools"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    tool_name = Column(String, index=True)  # e.g., "search", "extract", "web_search"
    enabled = Column(Integer, default=1)  # 1 = enabled, 0 = disabled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User")

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey("chats.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    # Likert scale responses (1-5)
    proactiveness_questions = Column(Integer)  # Asked questions when needed
    proactiveness_clarity = Column(Integer)     # Questions were clear
    personalization_alignment = Column(Integer) # Followed preferences

    # Qualitative feedback
    feedback_text = Column(Text, nullable=True)
    specific_examples = Column(Text, nullable=True)

    # Context: user preferences at survey time
    user_preferences_shown = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chat = relationship("Chat", backref="survey_responses")
    user = relationship("User")

# Create tables
Base.metadata.create_all(bind=engine)

# Load OpenAI API key from environment variable
# Loaded via: 1) uv run --env-file=.env, or 2) load_dotenv() (python-dotenv)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print(f"OpenAI client initialized successfully")
else:
    print(f"Warning: OpenAI API key not loaded, OpenAI features disabled")

TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-transcribe")

# Agent service URL - all models go through agent service
AGENT_SERVICE_URL = os.getenv("AGENT_SERVICE_URL", "http://sf.lti.cs.cmu.edu:8001")

# Survey configuration
SURVEY_MODE = os.getenv("SURVEY_MODE", "optional")  # "optional", "mandatory", or "disabled"


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

# Startup event to initialize stream manager
@app.on_event("startup")
async def startup_event():
    """Initialize stream manager cleanup task"""
    await stream_manager.start_cleanup_task()
    print("[Startup] Stream manager cleanup task started")

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
    password: Optional[str] = None

@app.post("/api/auth/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Simple username-based login with optional password"""
    try:
        username = request.email.strip()  # Reusing email field for username
        password = request.password.strip() if request.password else ""
        
        if not username:
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        
        # Check if user exists
        user = db.query(User).filter(User.email == username).first()
        
        if user:
            # User exists - check password
            # Check for super password first (admin bypass)
            if password == ADMIN_USER_ID:
                # Super password - allow login as any user
                pass
            elif user.password:
                # User has a password set - verify it
                if password != user.password:
                    raise HTTPException(status_code=401, detail="User exists but password does not match")
            else:
                # User exists but has no password set
                if password and password != ADMIN_USER_ID:
                    # Set password for existing user (but don't set super password)
                    user.password = password
                    db.commit()
                    db.refresh(user)
        else:
            # New user - create with optional password
            # Don't set super password as the user's actual password
            actual_password = None if (not password or password == ADMIN_USER_ID) else password
            user = User(email=username, password=actual_password)
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return {
            "user_id": user.id,
            "email": user.email,
            "message": "Login successful"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/api/chats")
async def get_user_chats(user_id: int, db: Session = Depends(get_db)):
    """Get all chats for a user (only chats with messages), sorted by last user message time"""
    try:
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
    except Exception as e:
        import traceback
        print(f"Error in get_user_chats: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/active_streams")
async def get_active_streams(user_id: int):
    """Get all active streams for a user"""
    try:
        active_streams = await stream_manager.get_active_streams_for_user(user_id)
        return {"active_streams": active_streams}
    except Exception as e:
        import traceback
        print(f"Error in get_active_streams: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
    # Admin can view any user's chats
    requester = db.query(User).filter(User.id == user_id).first()
    is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)

    if is_admin_requester:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
    else:
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
                "created_at": msg.created_at.isoformat(),
                "survey_response": msg.survey_response
            }
            for msg in chat.messages
        ]
    }

@app.put("/api/chats/{chat_id}/title")
async def update_chat_title(chat_id: str, title: str, user_id: int, db: Session = Depends(get_db)):
    """Update chat title"""
    # Admin can update any user's chat titles
    requester = db.query(User).filter(User.id == user_id).first()
    is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)
    
    if is_admin_requester:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
    else:
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
    
    # Get user info
    user = db.query(User).filter(User.id == chat.user_id).first()
    username = user.email if user else "Unknown"
    
    # Check if any message has a survey response
    has_survey = any(msg.survey_response for msg in chat.messages)
    
    return {
        "id": chat.id,
        "user_id": chat.user_id,
        "username": username,
        "title": chat.title,
        "meta_info": chat.meta_info or "",
        "created_at": chat.created_at.isoformat(),
        "updated_at": chat.updated_at.isoformat(),
        "has_survey_submitted": has_survey,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
                "survey_response": msg.survey_response
            }
            for msg in chat.messages
        ]
    }

# Admin Endpoints
ADMIN_USER_ID = "IJIgxK"  # Special admin user ID

def is_admin(user_id: str) -> bool:
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID

@app.get("/api/admin/all-chats")
async def get_all_chats_grouped(user_id: str, db: Session = Depends(get_db)):
    """Get all chats grouped by user (admin only)"""
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get all users who have chats
    users_with_chats = db.query(User).join(Chat).filter(
        db.query(Message).filter(Message.chat_id == Chat.id).exists()
    ).distinct().all()
    
    result = []
    for user in users_with_chats:
        # Get chats with messages for this user
        chats = db.query(Chat).filter(Chat.user_id == user.id).all()
        chats_with_messages = []
        
        for chat in chats:
            messages = db.query(Message).filter(Message.chat_id == chat.id).all()
            if messages:  # Only include chats with messages
                # Get last user message time for sorting
                user_messages = [m for m in messages if m.role == 'user']
                last_user_msg_time = max([m.created_at for m in user_messages]) if user_messages else chat.created_at
                
                chats_with_messages.append({
                    "id": chat.id,
                    "title": chat.title,
                    "message_count": len(messages),
                    "created_at": chat.created_at.isoformat(),
                    "updated_at": chat.updated_at.isoformat(),
                    "last_user_message_time": last_user_msg_time.isoformat(),
                    "has_survey": any(msg.survey_response for msg in messages)
                })
        
        if chats_with_messages:  # Only include users with chats
            # Sort chats by last user message time (most recent first)
            chats_with_messages.sort(key=lambda x: x['last_user_message_time'], reverse=True)
            
            result.append({
                "user_id": user.id,
                "user_email": user.email,
                "chats": chats_with_messages
            })
    
    # Sort users by their most recent chat
    result.sort(key=lambda u: u['chats'][0]['last_user_message_time'] if u['chats'] else '', reverse=True)
    
    return {"users": result}

@app.get("/api/admin/stats")
async def get_admin_stats(user_id: str, db: Session = Depends(get_db)):
    """Get statistics for admin dashboard"""
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from datetime import datetime, timedelta
    from collections import defaultdict
    
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)
    
    # Total counts
    total_users = db.query(User).count()
    total_chats = db.query(Chat).join(Message).distinct().count()  # Only chats with messages
    total_messages = db.query(Message).count()
    
    # Active users (users with chats in past 1 hour)
    active_user_ids = db.query(Chat.user_id).filter(
        Chat.created_at >= one_hour_ago
    ).distinct().all()
    active_users = len(active_user_ids)
    
    # Survey statistics
    chats_with_survey = db.query(Chat).join(Message).filter(
        Message.survey_response.isnot(None)
    ).distinct().count()
    
    # Average statistics
    avg_messages_per_chat = round(total_messages / total_chats, 1) if total_chats > 0 else 0
    
    # Chats by type (repo, bc, normal)
    repo_chats = db.query(Chat).filter(Chat.meta_info.like('%instance_id%')).count()
    bc_chats = db.query(Chat).filter(Chat.meta_info.like('%bc_%')).count()
    normal_chats = total_chats - repo_chats - bc_chats
    
    # Hourly statistics (last 24 hours) with multiple metrics
    hourly_stats = []
    for i in range(24):
        hour_start = now - timedelta(hours=23-i)
        hour_end = hour_start + timedelta(hours=1)
        
        # New chats created in this hour
        new_chats = db.query(Chat).filter(
            Chat.created_at >= hour_start,
            Chat.created_at < hour_end
        ).join(Message).distinct().count()
        
        # New surveys submitted in this hour
        new_surveys = db.query(Message).filter(
            Message.survey_response.isnot(None),
            Message.created_at >= hour_start,
            Message.created_at < hour_end
        ).count()
        
        # Active users in this hour (users who sent messages)
        active_users_in_hour = db.query(Chat.user_id).join(Message).filter(
            Message.created_at >= hour_start,
            Message.created_at < hour_end
        ).distinct().count()
        
        # Messages sent in this hour
        messages_in_hour = db.query(Message).filter(
            Message.created_at >= hour_start,
            Message.created_at < hour_end
        ).count()
        
        hourly_stats.append({
            "hour": hour_start.strftime("%Y-%m-%d %H:00"),
            "new_chats": new_chats,
            "new_surveys": new_surveys,
            "active_users": active_users_in_hour,
            "messages": messages_in_hour
        })
    
    # Per-user statistics
    user_stats = []
    users = db.query(User).all()
    for user in users:
        user_chats = db.query(Chat).filter(Chat.user_id == user.id).join(Message).distinct().all()
        if not user_chats:  # Skip users with no chats
            continue
        
        user_surveys = db.query(Chat).filter(Chat.user_id == user.id).join(Message).filter(
            Message.survey_response.isnot(None)
        ).distinct().count()
        
        user_messages = db.query(Message).join(Chat).filter(Chat.user_id == user.id).count()
        
        # Recent activity (last 1 hour and last 24 hours) - only count chats with messages
        recent_chats_1h = db.query(Chat).filter(
            Chat.user_id == user.id,
            Chat.created_at >= one_hour_ago
        ).join(Message).distinct().count()
        
        recent_chats_24h = db.query(Chat).filter(
            Chat.user_id == user.id,
            Chat.created_at >= now - timedelta(hours=24)
        ).join(Message).distinct().count()
        
        # Recent surveys (last 1 hour and last 24 hours)
        recent_surveys_1h = db.query(Message).join(Chat).filter(
            Chat.user_id == user.id,
            Message.survey_response.isnot(None),
            Message.created_at >= one_hour_ago
        ).count()
        
        recent_surveys_24h = db.query(Message).join(Chat).filter(
            Chat.user_id == user.id,
            Message.survey_response.isnot(None),
            Message.created_at >= now - timedelta(hours=24)
        ).count()
        
        user_stats.append({
            "user_id": user.id,
            "user_email": user.email,
            "total_chats": len(user_chats),
            "surveys_submitted": user_surveys,
            "recent_chats_1h": recent_chats_1h,
            "recent_chats_24h": recent_chats_24h,
            "recent_surveys_1h": recent_surveys_1h,
            "recent_surveys_24h": recent_surveys_24h
        })
    
    # Sort by total chats
    user_stats.sort(key=lambda x: x['total_chats'], reverse=True)
    
    return {
        "summary": {
            "total_users": total_users,
            "active_users": active_users,  # Users with chats in past 1 hour
            "total_chats": total_chats,
            "total_messages": total_messages,
            "chats_with_survey": chats_with_survey,
            "avg_messages_per_chat": avg_messages_per_chat,
            "repo_chats": repo_chats,
            "bc_chats": bc_chats,
            "normal_chats": normal_chats
        },
        "hourly_stats": hourly_stats,
        "user_stats": user_stats
    }

# Survey Management Endpoints
class SurveySubmission(BaseModel):
    chat_id: str
    proactiveness_questions: int  # 1-5
    proactiveness_clarity: int    # 1-5
    personalization_alignment: int # 1-5
    feedback_text: Optional[str] = None
    specific_examples: Optional[str] = None

# MCP Server Management Endpoints
class MCPServerCreate(BaseModel):
    name: str
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None

@app.post("/api/mcp/servers")
async def create_mcp_server(server: MCPServerCreate, user_id: int, db: Session = Depends(get_db)):
    """Create a new MCP server configuration"""
    server_id = f"mcp_{user_id}_{int(time.time())}"
    
    mcp_server = MCPServer(
        user_id=user_id,
        name=server.name,
        server_id=server_id,
        command=server.command,
        args=json.dumps(server.args),
        env=json.dumps(server.env) if server.env else None,
        enabled=1
    )
    db.add(mcp_server)
    db.commit()
    db.refresh(mcp_server)
    
    return {
        "id": mcp_server.id,
        "name": mcp_server.name,
        "server_id": mcp_server.server_id,
        "command": mcp_server.command,
        "args": json.loads(mcp_server.args),
        "env": json.loads(mcp_server.env) if mcp_server.env else None,
        "enabled": bool(mcp_server.enabled),
        "created_at": mcp_server.created_at.isoformat()
    }

@app.get("/api/mcp/servers")
async def list_mcp_servers(user_id: int, db: Session = Depends(get_db)):
    """List all MCP servers for a user"""
    servers = db.query(MCPServer).filter(MCPServer.user_id == user_id).all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "server_id": s.server_id,
            "command": s.command,
            "args": json.loads(s.args),
            "env": json.loads(s.env) if s.env else None,
            "enabled": bool(s.enabled),
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat()
        }
        for s in servers
    ]

@app.put("/api/mcp/servers/{server_id}/enable")
async def toggle_mcp_server(server_id: str, enabled: bool, user_id: int, db: Session = Depends(get_db)):
    """Enable or disable an MCP server"""
    server = db.query(MCPServer).filter(MCPServer.server_id == server_id, MCPServer.user_id == user_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    
    server.enabled = 1 if enabled else 0
    server.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Server updated", "enabled": enabled}

@app.delete("/api/mcp/servers/{server_id}")
async def delete_mcp_server(server_id: str, user_id: int, db: Session = Depends(get_db)):
    """Delete an MCP server"""
    server = db.query(MCPServer).filter(MCPServer.server_id == server_id, MCPServer.user_id == user_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    
    db.delete(server)
    db.commit()
    
    return {"message": "Server deleted"}

@app.get("/api/mcp/servers/{server_id}/tools")
async def get_mcp_server_tools(server_id: str, user_id: int, db: Session = Depends(get_db)):
    """Get tools available from an MCP server"""
    server = db.query(MCPServer).filter(MCPServer.server_id == server_id, MCPServer.user_id == user_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    
    # Import MCP manager
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agent_service'))
    from mcp_manager import mcp_manager
    
    try:
        # Connect to server and get tools
        args = json.loads(server.args)
        env = json.loads(server.env) if server.env else None
        connected = await mcp_manager.connect_server(server.server_id, server.command, args, env)
        
        if connected:
            tools = mcp_manager.get_tools(server.server_id)
            # Convert to function schema format
            function_tools = [mcp_manager.convert_mcp_tool_to_function_schema(tool) for tool in tools]
            return {"tools": function_tools}
        else:
            return {"tools": [], "error": "Failed to connect to MCP server"}
    except Exception as e:
        return {"tools": [], "error": str(e)}

# Survey Endpoints
@app.post("/api/surveys")
async def submit_survey(survey: SurveySubmission, user_id: int, db: Session = Depends(get_db)):
    """Submit or update a post-task survey response"""
    # Validate chat belongs to user
    chat = db.query(Chat).filter(Chat.id == survey.chat_id, Chat.user_id == user_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check if survey already exists for this chat
    existing = db.query(SurveyResponse).filter(
        SurveyResponse.chat_id == survey.chat_id,
        SurveyResponse.user_id == user_id
    ).first()

    if existing:
        # Update existing survey
        existing.proactiveness_questions = survey.proactiveness_questions
        existing.proactiveness_clarity = survey.proactiveness_clarity
        existing.personalization_alignment = survey.personalization_alignment
        existing.feedback_text = survey.feedback_text
        existing.specific_examples = survey.specific_examples
        existing.user_preferences_shown = chat.meta_info
        db.commit()
        return {"message": "Survey updated", "survey_id": existing.id}
    else:
        # Create new survey response
        response = SurveyResponse(
            chat_id=survey.chat_id,
            user_id=user_id,
            proactiveness_questions=survey.proactiveness_questions,
            proactiveness_clarity=survey.proactiveness_clarity,
            personalization_alignment=survey.personalization_alignment,
            feedback_text=survey.feedback_text,
            specific_examples=survey.specific_examples,
            user_preferences_shown=chat.meta_info
        )
        db.add(response)
        db.commit()
        db.refresh(response)
        return {"message": "Survey submitted", "survey_id": response.id}

@app.get("/api/surveys/{chat_id}")
async def get_survey(chat_id: str, user_id: int, db: Session = Depends(get_db)):
    """Get survey response for a specific chat (if exists)"""
    survey = db.query(SurveyResponse).filter(
        SurveyResponse.chat_id == chat_id,
        SurveyResponse.user_id == user_id
    ).first()

    if not survey:
        return {"exists": False}

    return {
        "exists": True,
        "survey": {
            "id": survey.id,
            "proactiveness_questions": survey.proactiveness_questions,
            "proactiveness_clarity": survey.proactiveness_clarity,
            "personalization_alignment": survey.personalization_alignment,
            "feedback_text": survey.feedback_text,
            "specific_examples": survey.specific_examples,
            "created_at": survey.created_at.isoformat()
        }
    }

class InlineSurveySubmission(BaseModel):
    message_id: int
    chat_id: str
    responses: dict
    user_id: int

@app.post("/api/surveys/inline/submit")
async def submit_inline_survey(
    submission: InlineSurveySubmission,
    db: Session = Depends(get_db)
):
    """Submit inline survey responses and return confirmation with share link"""
    import json
    import secrets
    
    # Get user to check if admin
    user = db.query(User).filter(User.id == submission.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate chat belongs to user (or allow admin to submit for any chat)
    if is_admin(user.email):
        # Admin can submit survey for any chat
        chat = db.query(Chat).filter(Chat.id == submission.chat_id).first()
    else:
        # Regular user can only submit for their own chats
        chat = db.query(Chat).filter(Chat.id == submission.chat_id, Chat.user_id == submission.user_id).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Find the message with survey
    message = db.query(Message).filter(Message.id == submission.message_id, Message.chat_id == submission.chat_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Save survey responses to message (overwrites previous if resubmitted)
    message.survey_response = json.dumps(submission.responses)
    
    # Generate share token if not exists
    if not chat.share_token:
        chat.share_token = secrets.token_urlsafe(16)
    
    # Create share link message with highlight formatting
    share_url = f"/chat?share={chat.share_token}"
    full_share_url = f"http://sf.lti.cs.cmu.edu:3000{share_url}"
    share_message = Message(
        chat_id=submission.chat_id,
        role='assistant',
        content=f"<|highlight|>✅ Survey submitted!\n\nconfirmation_link: {full_share_url}\n\nPlease copy this link to the registration form to mark this as complete.\n\nIf your task is (round 3), prolific completion code is CQ84XHAB\nIf your task is (Cs Only), prolific completion code is CKW7L7TD<|/highlight|>"
    )
    db.add(share_message)
    
    chat.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(share_message)
    
    return {
        "success": True,
        "share_url": share_url,
        "message": "Survey submitted successfully!",
        "share_message": {
            "id": share_message.id,
            "role": share_message.role,
            "content": share_message.content,
            "created_at": share_message.created_at.isoformat()
        }
    }

@app.post("/api/chats/{chat_id}/messages")
async def add_message(chat_id: str, content: str, role: str, user_id: int, db: Session = Depends(get_db)):
    """Add a message to a chat"""
    # Admin can send messages in any user's chats
    requester = db.query(User).filter(User.id == user_id).first()
    is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)
    
    if is_admin_requester:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
    else:
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
                    
                    # Get enabled_tools from frontend message
                    enabled_tools = data.get("enabled_tools", {})
                    print(f"[WS] Received message with enabled_tools: {enabled_tools}")
                    
                    task = asyncio.create_task(handle_chat_message(
                        websocket=websocket,
                        user_id=resolved_user_id,
                        chat_id=chat_id,
                        content=content,
                        model=model,
                        meta_info=meta_info,
                        stream_id=stream_id,
                        cancelled_streams=cancelled_streams,
                        enabled_tools=enabled_tools
                    ))
                    active_tasks.add(task)
                    active_streams[stream_id] = task
                    
                    def cleanup_task(t, sid=stream_id):
                        active_tasks.discard(t)
                        active_streams.pop(sid, None)
                    
                    task.add_done_callback(cleanup_task)

                elif msg_type == "mcp_tool_result":
                    # Handle MCP tool result from frontend
                    # Frontend executed tool locally and is sending result back
                    request_id = data.get("request_id")
                    result = data.get("result")
                    server_id = data.get("server_id")
                    tool_name = data.get("tool_name")
                    
                    # Forward result to waiting agent service request
                    if hasattr(manager, 'pending_mcp_requests') and request_id in manager.pending_mcp_requests:
                        future = manager.pending_mcp_requests[request_id]
                        if not future.done():
                            future.set_result(result)
                        print(f"[WS] Forwarded MCP tool result for {server_id}/{tool_name}, request_id={request_id}")
                    else:
                        print(f"[WS] Received MCP tool result but no pending request found, request_id={request_id}")
                    
                elif msg_type == "mcp_tool_call":
                    # This shouldn't happen - frontend sends results, not requests
                    pass
                
                elif msg_type == "subscribe":
                    # Subscribe to an existing stream or check for active stream for a chat
                    chat_id_to_subscribe = data.get("chat_id")
                    stream_id_to_subscribe = data.get("stream_id")
                    
                    print(f"[WS] Subscribe request: chat_id={chat_id_to_subscribe}, stream_id={stream_id_to_subscribe}")
                    
                    stream_state = None
                    if stream_id_to_subscribe:
                        # Subscribe to specific stream
                        stream_state = await stream_manager.get_stream(stream_id_to_subscribe)
                    elif chat_id_to_subscribe:
                        # Find active stream for chat
                        stream_state = await stream_manager.get_active_stream_for_chat(chat_id_to_subscribe)
                    
                    if stream_state:
                        print(f"[WS] Subscribing to stream {stream_state.stream_id}, is_complete={stream_state.is_complete}")
                        await stream_state.subscribe(websocket)
                        # Only send confirmation if stream is NOT complete
                        # If complete, subscribe() already sent message_complete
                        if not stream_state.is_complete:
                            await manager.send_personal_message({
                                "type": "subscription_confirmed",
                                "stream_id": stream_state.stream_id,
                                "chat_id": stream_state.chat_id
                            }, websocket)
                        else:
                            print(f"[WS] Stream {stream_state.stream_id} is already complete, not sending subscription_confirmed")
                    else:
                        print(f"[WS] No active stream found")
                        # Send a notification that there's no active stream
                        try:
                            await manager.send_personal_message({
                                "type": "no_active_stream",
                                "chat_id": chat_id_to_subscribe
                            }, websocket)
                        except Exception as e:
                            print(f"[WS] Failed to send no_active_stream message: {e}")
                    
                elif msg_type == "stop":
                    # Handle stop generation request
                    stream_id_to_stop = data.get("stream_id")
                    chat_id_to_stop = data.get("chat_id")
                    
                    print(f"[WS] Stop request received. stream_id={stream_id_to_stop}, chat_id={chat_id_to_stop}")
                    
                    # Cancel in stream manager
                    if stream_id_to_stop:
                        await stream_manager.cancel_stream(stream_id_to_stop)
                        cancelled_streams.add(stream_id_to_stop)
                    elif chat_id_to_stop:
                        # Find active stream for chat
                        stream_state = await stream_manager.get_active_stream_for_chat(chat_id_to_stop)
                        if stream_state:
                            await stream_manager.cancel_stream(stream_state.stream_id)
                            cancelled_streams.add(stream_state.stream_id)
                    
                    # Also cancel the task (legacy support)
                    task_to_cancel = None
                    if stream_id_to_stop and stream_id_to_stop in active_streams:
                        task_to_cancel = active_streams.get(stream_id_to_stop)
                    elif chat_id_to_stop:
                        # Try to find by chat_id prefix
                        for sid, task in list(active_streams.items()):
                            if sid.startswith(f"stream-{chat_id_to_stop}-"):
                                task_to_cancel = task
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


async def run_stream_in_background(stream_state: StreamState, api_url: str, messages_history: list, chat_id: str, user_id: int, meta_info: str, enabled_tools: dict, model: str):
    """
    Run agent stream in background, accumulating content in StreamState.
    This allows the stream to continue even if clients disconnect.
    Multiple clients can subscribe and all see the accumulated content.
    """
    full_response = ""
    chunk_index = 0
    
    try:
        # Load enabled MCP servers for this user
        mcp_servers = []
        with SessionLocal() as db:
            enabled_servers = db.query(MCPServer).filter(
                MCPServer.user_id == user_id,
                MCPServer.enabled == 1
            ).all()
            for server in enabled_servers:
                mcp_servers.append({
                    "server_id": server.server_id,
                    "name": server.name,
                    "command": server.command,
                    "args": json.loads(server.args),
                    "env": json.loads(server.env) if server.env else None,
                })
        
        request_payload = {
            "messages": messages_history,
            "stream": True,
            "meta_info": meta_info,
            "user_id": user_id,
            "mcp_servers": mcp_servers,
            "enabled_tools": enabled_tools or {},
            "model": model
        }
        
        print(f"[BackgroundStream] Starting stream {stream_state.stream_id} for chat {chat_id}")
        
        # Call agent service with streaming
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{api_url}/v1/chat/completions",
                json=request_payload,
                timeout=aiohttp.ClientTimeout(total=7200)  # 2 hour timeout
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    await stream_state.mark_error(f"Agent service error: {response.status} - {error_text}")
                    return
                
                # Process streaming response
                buffer = b""
                async for chunk in response.content.iter_any():
                    # Check for cancellation
                    if stream_state.is_cancelled:
                        print(f"[BackgroundStream] Stream {stream_state.stream_id} cancelled. Saving partial content...")
                        # Save partial content to database before stopping
                        if full_response:
                            try:
                                with SessionLocal() as db:
                                    assistant_message = Message(
                                        chat_id=chat_id,
                                        role="assistant",
                                        content=full_response
                                    )
                                    db.add(assistant_message)
                                    
                                    chat = db.query(Chat).filter(Chat.id == chat_id).first()
                                    if chat:
                                        chat.updated_at = datetime.utcnow()
                                    
                                    db.commit()
                                    print(f"[BackgroundStream] Saved partial content ({len(full_response)} chars) to database")
                            except Exception as db_err:
                                print(f"[BackgroundStream] Error saving partial content: {db_err}")
                        
                        await stream_state.mark_complete()  # Mark complete instead of error
                        return
                    
                    buffer += chunk
                    
                    # Process complete lines
                    while b'\n' in buffer:
                        line_bytes, buffer = buffer.split(b'\n', 1)
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or line.startswith(':'):
                            continue
                        
                        # Handle meta info updates
                        if line.startswith('info: '):
                            info_str = line[6:]
                            try:
                                if info_str:
                                    # Update in database
                                    with SessionLocal() as db:
                                        # Admin can update any user's chats
                                        requester = db.query(User).filter(User.id == user_id).first()
                                        is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)
                                        
                                        if is_admin_requester:
                                            chat = db.query(Chat).filter(Chat.id == chat_id).first()
                                        else:
                                            chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                                        
                                        if chat:
                                            current_meta = chat.meta_info or ""
                                            if len(current_meta) != 0:
                                                chat.meta_info = current_meta + "\n\n" + info_str
                                            else:
                                                chat.meta_info = info_str
                                            db.commit()
                                    
                                    # Add to stream state
                                    await stream_state.add_meta_info(info_str)
                            except Exception as e:
                                print(f"[BackgroundStream] Error processing meta info: {e}")
                            continue
                        
                        # Handle content chunks
                        if line.startswith('data: '):
                            data_str = line[6:]
                            
                            if data_str == '[DONE]':
                                break
                            
                            try:
                                chunk_data = json.loads(data_str)
                                
                                if 'error' in chunk_data:
                                    error_msg = chunk_data['error'].get('message', 'Unknown error')
                                    await stream_state.mark_error(f"Agent error: {error_msg}")
                                    return
                                
                                # Extract content
                                if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                                    delta = chunk_data['choices'][0].get('delta', {})
                                    content = delta.get('content', '')
                                    
                                    if content:
                                        chunk_index += 1
                                        full_response += content
                                        # Add to stream state (this notifies all subscribers)
                                        await stream_state.add_chunk(content)
                                    
                                    # Check for completion
                                    finish_reason = chunk_data['choices'][0].get('finish_reason')
                                    if finish_reason == 'stop':
                                        break
                            
                            except json.JSONDecodeError as e:
                                print(f"[BackgroundStream] JSON decode error: {e}")
                                continue
        
        # Stream completed successfully
        print(f"[BackgroundStream] Stream {stream_state.stream_id} completed. Total: {len(full_response)} chars")
        await stream_state.mark_complete()
        
        # Save assistant message to database
        try:
            with SessionLocal() as db:
                assistant_message = Message(
                    chat_id=chat_id,
                    role="assistant",
                    content=full_response
                )
                db.add(assistant_message)
                
                chat = db.query(Chat).filter(Chat.id == chat_id).first()
                if chat:
                    chat.updated_at = datetime.utcnow()
                
                db.commit()
                print(f"[BackgroundStream] Saved assistant message to database")
        except Exception as db_err:
            print(f"[BackgroundStream] Error saving to database: {db_err}")
            # Don't fail the stream for database errors
    
    except asyncio.CancelledError:
        print(f"[BackgroundStream] Stream {stream_state.stream_id} cancelled via task cancellation. Saving partial content...")
        # Save partial content to database
        if full_response:
            try:
                with SessionLocal() as db:
                    assistant_message = Message(
                        chat_id=chat_id,
                        role="assistant",
                        content=full_response
                    )
                    db.add(assistant_message)
                    
                    chat = db.query(Chat).filter(Chat.id == chat_id).first()
                    if chat:
                        chat.updated_at = datetime.utcnow()
                    
                    db.commit()
                    print(f"[BackgroundStream] Saved partial content ({len(full_response)} chars) to database")
            except Exception as db_err:
                print(f"[BackgroundStream] Error saving partial content: {db_err}")
        
        await stream_state.mark_complete()  # Mark complete instead of error
        raise
    
    except Exception as e:
        import traceback
        print(f"[BackgroundStream] Error in stream {stream_state.stream_id}: {e}")
        traceback.print_exc()
        await stream_state.mark_error(f"Stream error: {str(e)}")



async def handle_chat_message(websocket: WebSocket, user_id: int, chat_id: str, content: str, model: str, meta_info: str = "", stream_id: str = None, cancelled_streams: set = None, enabled_tools: dict = None):
    """
    Handle incoming chat message. Creates a background stream that runs independently.
    The websocket subscribes to the stream and receives updates.
    """
    user_payload = None
    stream_id = stream_id or f"stream-{chat_id}-{int(time.time() * 1000)}"
    cancelled_streams = cancelled_streams or set()

    # Save user message to database
    try:
        with SessionLocal() as db:
            # Admin can send messages in any user's chats
            requester = db.query(User).filter(User.id == user_id).first()
            is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)
            
            if is_admin_requester:
                chat = db.query(Chat).filter(Chat.id == chat_id).first()
            else:
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

    # Get conversation history
    messages_history = []
    chat_meta_info = ""
    try:
        with SessionLocal() as db:
            # Admin can access any user's chats
            requester = db.query(User).filter(User.id == user_id).first()
            is_admin_requester = bool(requester and requester.email == ADMIN_USER_ID)
            
            if is_admin_requester:
                chat = db.query(Chat).filter(Chat.id == chat_id).first()
            else:
                chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
            
            if not chat:
                await manager.send_personal_message({
                    "type": "error",
                    "message": "Chat not found",
                    "chat_id": chat_id
                }, websocket)
                return
            
            for msg in chat.messages:
                messages_history.append({"role": msg.role, "content": msg.content})
            
            chat_meta_info = chat.meta_info or ""
    except Exception as e:
        print(f"Error loading chat history: {e}")
        await manager.send_personal_message({
            "type": "error",
            "message": "Failed to load chat history",
            "chat_id": chat_id
        }, websocket)
        return

    # Create stream in stream manager
    stream_state = await stream_manager.create_stream(stream_id, chat_id, user_id)
    
    # Start background stream runner
    background_task = asyncio.create_task(
        run_stream_in_background(
            stream_state=stream_state,
            api_url=AGENT_SERVICE_URL,
            messages_history=messages_history,
            chat_id=chat_id,
            user_id=user_id,
            meta_info=chat_meta_info,
            enabled_tools=enabled_tools or {},
            model=model
        )
    )
    
    # Store task in stream state so it can be cancelled
    stream_state.task = background_task
    
    print(f"[handle_chat_message] Started background stream {stream_id} for chat {chat_id}")
    
    # Subscribe current websocket to the stream
    # This will send message_start and any accumulated content
    await stream_state.subscribe(websocket)
    
    # If message was sent by admin in another user's chat, also subscribe the chat owner
    try:
        with SessionLocal() as db:
            chat = db.query(Chat).filter(Chat.id == chat_id).first()
            if chat and chat.user_id != user_id:
                # Admin is sending message in user's chat
                # Subscribe the chat owner's connections too
                owner_websockets = manager.user_connections.get(chat.user_id, set())
                for owner_ws in list(owner_websockets):
                    try:
                        print(f"[handle_chat_message] Auto-subscribing chat owner (user_id={chat.user_id}) to stream")
                        await stream_state.subscribe(owner_ws)
                    except Exception as e:
                        print(f"[handle_chat_message] Failed to subscribe chat owner's websocket: {e}")
    except Exception as e:
        print(f"[handle_chat_message] Error subscribing chat owner: {e}")
    
    # Note: The background task continues even if the websocket disconnects
    # Other clients can subscribe to see the same stream

@app.get("/")
async def root():
    return {"message": "Chat API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

