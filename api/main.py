from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import os
from common.database.db import Database

# 1. Setup Socket.IO
# asyncio_mode='asgi' is important for integration with FastAPI/Uvicorn
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio)

# 2. Setup FastAPI
app = FastAPI(title="Ethereal Trifid API")

@app.get("/")
async def root():
    from common.version import get_version
    return {"message": "Ethereal Trifid API", "version": get_version()}

# Mount Socket.IO
# Note: In standard ASGI mounts, check path issues. 
# Usually socketio.ASGIApp wraps the FastAPI app or vice versa.
# Using 'mount' is easier for /socket.io path handling.
app.mount("/socket.io", socket_app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Lifecycle Events
@app.on_event("startup")
async def startup_db():
    print("API Starting up...")
    try:
        await Database.get_pool()
        print("Database connected.")
    except Exception as e:
        print(f"Failed to connect to DB: {e}")

@app.on_event("shutdown")
async def shutdown_db():
    print("API Shutting down...")
    await Database.close()

# 4. Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Socket Connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Socket Disconnected: {sid}")

@sio.event
async def join_session(sid, data):
    # data: {'session_id': 'uuid'}
    session_id = data.get('session_id')
    if session_id:
        room = f"session_{session_id}"
        sio.enter_room(sid, room)
        print(f"Socket {sid} joined room {room}")

@sio.event
async def create_session(sid, data):
    # From Bot: {'session_id': '...', 'host_id': ...}
    session_id = data.get('session_id')
    print(f"Session Created Event received for {session_id}")
    # Logic to maybe notify global listeners?

@sio.event
async def play_video(sid, data):
    # From Bot/Host: {'session_id': '...', 'url': '...'}
    session_id = data.get('session_id')
    url = data.get('url')
    room = f"session_{session_id}"
    print(f"Broadcasting play_video to {room}: {url}")
    await sio.emit('sync_video', {'action': 'play', 'url': url}, room=room)

@sio.event
async def seek_video(sid, data):
    session_id = data.get('session_id')
    timestamp = data.get('timestamp')
    room = f"session_{session_id}"
    await sio.emit('sync_video', {'action': 'seek', 'timestamp': timestamp}, room=room)

@sio.event
async def pause_video(sid, data):
    session_id = data.get('session_id')
    room = f"session_{session_id}"
    await sio.emit('sync_video', {'action': 'pause'}, room=room)

# 5. Include Routers
from routers import users
app.include_router(users.router)
