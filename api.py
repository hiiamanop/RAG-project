from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from chat_database import ChatDatabase
import os

app = FastAPI(title="Chat History API", description="API for managing chat history with MongoDB")

# Initialize DB (expecting MONGODB_URI in env or defaults)
# For demo purposes, if no URI, we might fail or use a default.
# Ensure MONGODB_URI is set in .env before running.
db = ChatDatabase()

class MessageCreate(BaseModel):
    user_id: str
    room_id: str
    role: str
    content: str

class MessageResponse(BaseModel):
    id: str
    user_id: str
    room_id: str
    role: str
    content: str
    timestamp: str
    is_deleted: bool

@app.post("/messages/", response_model=Dict[str, str])
def create_message(message: MessageCreate):
    msg_id = db.save_message(
        user_id=message.user_id,
        room_id=message.room_id,
        role=message.role,
        content=message.content
    )
    if not msg_id:
        raise HTTPException(status_code=500, detail="Database not connected")
    return {"id": str(msg_id), "status": "saved"}

@app.get("/messages/{room_id}", response_model=List[MessageResponse])
def get_messages(
    room_id: str, 
    limit: int = Query(50, ge=1, le=100), 
    skip: int = Query(0, ge=0)
):
    messages = db.get_history(room_id, limit, skip)
    results = []
    for msg in messages:
        results.append(MessageResponse(
            id=msg["_id"],
            user_id=msg["user_id"],
            room_id=msg["room_id"],
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"].isoformat(),
            is_deleted=msg["is_deleted"]
        ))
    return results

@app.delete("/messages/{message_id}")
def delete_message(message_id: str):
    success = db.soft_delete_message(message_id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"status": "deleted"}
