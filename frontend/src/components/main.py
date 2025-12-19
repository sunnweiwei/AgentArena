from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File
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
from openai import OpenAI

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("User", back_populates="chats")
    messages = relationship("Message", back_populates="chat", order_by="Message.created_at")

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

TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")

# Model mapping
MODEL_MAP = {
    "Auto": "gpt-5-nano",  # Default to GPT-5-Nano unless overridden
    "GPT-5-Nano": "gpt-5-nano",
    "GPT-5-Mini": "gpt-5-mini"
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
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://sf.lti.cs.cmu.edu:3000",
    "http://sf.lti.cs.cmu.edu",
    "http://localhost:4173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
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
            
            # Transcribe using OpenAI
            selected_model = model or TRANSCRIPTION_MODEL
            print(f"[Transcribe] Using model: {selected_model}")
            with open(tmp_file_path, "rb") as audio_file:
                transcription = openai_client.audio.transcriptions.create(
                    model=selected_model,
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

                    if not chat_id:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "chat_id is required"
                        }, websocket)
                        continue

                    if not content:
                        continue

                    task = asyncio.create_task(handle_chat_message(
                        websocket=websocket,
                        user_id=resolved_user_id,
                        chat_id=chat_id,
                        content=content,
                        model=model
                    ))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)

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


async def handle_chat_message(websocket: WebSocket, user_id: int, chat_id: str, content: str, model: str):
    user_payload = None

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
        
        if openai_model is None or openai_client is None:
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
                
                # Build message history with system prompt
                messages_history = [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Always respond in English. When creating tables, use proper Markdown table syntax (| Column | Column |) instead of ASCII art tables. Format your responses clearly with proper Markdown formatting."
                    }
                ]
                messages_history.extend([
                    {"role": msg.role, "content": msg.content}
                    for msg in chat.messages[-10:]  # Last 10 messages for context
                ])
                messages_history.append({"role": "user", "content": content})

            # Start streaming response
            stream_id = str(uuid.uuid4())
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

                while True:
                    event_type, payload = await stream_queue.get()
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
                    await worker_task

                # Save complete message to database
                with SessionLocal() as db:
                    chat = db.query(Chat).filter(Chat.id == chat_id, Chat.user_id == user_id).first()
                    if not chat:
                        await manager.send_personal_message({
                            "type": "error",
                            "message": "Chat not found",
                            "chat_id": chat_id
                        }, websocket)
                        return

                    agent_message = Message(chat_id=chat_id, role="assistant", content=full_response)
                    db.add(agent_message)
                    chat.updated_at = datetime.utcnow()
                    db.commit()

                    # Send message complete with ID
                    print(f"Streaming response completed for chat {chat_id} (stream {stream_id})")
                    await manager.send_personal_message({
                        "type": "message_complete",
                        "id": agent_message.id,
                        "role": "assistant",
                        "content": full_response,
                        "created_at": agent_message.created_at.isoformat(),
                        "stream_id": stream_id,
                        "chunk_count": chunk_index,
                        "chat_id": chat_id
                    }, websocket)

            except Exception as openai_err:
                print(f"OpenAI API error: {openai_err}")
                import traceback
                traceback.print_exc()
                error_msg = str(openai_err)
                await manager.send_personal_message({
                    "type": "error",
                    "message": f"Error calling OpenAI: {error_msg}",
                    "stream_id": locals().get('stream_id'),
                    "chat_id": chat_id
                }, websocket)
                # Also send message_complete to close the streaming message
                await manager.send_personal_message({
                    "type": "message_complete",
                    "id": None,
                    "role": "assistant",
                    "content": f"Error: {error_msg}",
                    "created_at": datetime.utcnow().isoformat(),
                    "chat_id": chat_id
                }, websocket)

    except Exception as agent_err:
        print(f"Error generating agent response: {agent_err}")
        import traceback
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

