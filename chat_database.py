from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from datetime import datetime, timezone
import os
import uuid
from typing import List, Dict, Optional

class ChatDatabase:
    def __init__(self, uri: Optional[str] = None, db_name: str = "gdrive_chatbot"):
        """
        Initialize MongoDB connection.
        If uri is None, it tries to get from environment variable MONGODB_URI.
        If that's also missing, it raises an error (or could fallback to mock for dev).
        """
        self.uri = uri or os.getenv("MONGODB_URI")
        self.client = None
        self.db = None
        self.messages = None
        
        # Connect to DB
        if self.uri:
            try:
                self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
                # Check connection
                self.client.admin.command('ping')
                print("Connected to MongoDB")
            except ConnectionFailure:
                print("Failed to connect to MongoDB. Running in offline/mock mode if configured.")
                # In a real app, you might want to raise here.
        else:
            print("No MongoDB URI provided. Please set MONGODB_URI in .env")
            # For this MVP, we will rely on the user providing it, or handle gracefully.

        if self.client:
            self.db = self.client[db_name]
            self.messages = self.db['chat_messages']
            self._create_indexes()

    def _create_indexes(self):
        """
        Create indexes for optimization.
        - user_id: for filtering by user
        - room_id: for filtering by chat room
        - timestamp: for sorting and retention policy
        """
        if self.messages is not None:
            self.messages.create_index([("user_id", ASCENDING)])
            self.messages.create_index([("room_id", ASCENDING)])
            self.messages.create_index([("timestamp", DESCENDING)])
            # Compound index for common query: Get history for a room sorted by time
            self.messages.create_index([("room_id", ASCENDING), ("timestamp", DESCENDING)])

    def save_message(self, user_id: str, room_id: str, role: str, content: str) -> str:
        """
        Save a new message.
        """
        if self.messages is None:
            return str(uuid.uuid4()) # Return fake ID if no DB

        message = {
            "_id": str(uuid.uuid4()),
            "user_id": user_id,
            "room_id": room_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            "is_deleted": False
        }
        result = self.messages.insert_one(message)
        return result.inserted_id

    def get_history(self, room_id: str, limit: int = 50, skip: int = 0) -> List[Dict]:
        """
        Get chat history for a room with pagination.
        """
        if self.messages is None:
            return []

        cursor = self.messages.find(
            {"room_id": room_id, "is_deleted": False}
        ).sort("timestamp", ASCENDING).skip(skip).limit(limit)
        
        return list(cursor)

    def soft_delete_message(self, message_id: str) -> bool:
        """
        Soft delete a message by setting is_deleted=True.
        """
        if self.messages is None:
            return False

        result = self.messages.update_one(
            {"_id": message_id},
            {"$set": {"is_deleted": True}}
        )
        return result.modified_count > 0

    def enforce_retention_policy(self, days: int = 30):
        """
        Delete messages older than X days.
        This is a hard delete for compliance/storage optimization.
        """
        if self.messages is None:
            return 0

        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
        # Convert timestamp back to datetime if needed, or if stored as datetime object:
        # MongoDB stores datetime objects natively.
        cutoff_date = datetime.fromtimestamp(cutoff, timezone.utc)

        result = self.messages.delete_many({
            "timestamp": {"$lt": cutoff_date}
        })
        return result.deleted_count
