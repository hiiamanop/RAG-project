from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure
from datetime import datetime, timezone
import uuid
from typing import List, Dict, Optional
import logging
from src.core.config import settings

logger = logging.getLogger(__name__)

class ChatRepository:
    def __init__(self, uri: Optional[str] = None, db_name: str = "gdrive_chatbot"):
        """
        Initialize MongoDB connection.
        """
        self.uri = uri or settings.MONGODB_URI
        self.db_name = db_name or settings.DB_NAME
        self.client = None
        self.db = None
        self.collection = None
        
        # Connect to DB
        if self.uri:
            try:
                self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
                # Check connection
                self.client.admin.command('ping')
                logger.info("Connected to MongoDB")
                
                self.db = self.client[self.db_name]
                self.collection = self.db['chat_messages']
                self._create_indexes()
                
            except ConnectionFailure:
                logger.error("Failed to connect to MongoDB. Running in offline/mock mode.")
                self.client = None
        else:
            logger.warning("No MongoDB URI provided.")

    def _create_indexes(self):
        """
        Create indexes for optimization.
        """
        if self.collection is not None:
            # Compound index for common query: Get history for a room sorted by time
            self.collection.create_index([("room_id", ASCENDING), ("timestamp", DESCENDING)])
            self.collection.create_index([("user_id", ASCENDING)])
            # TTL Index for auto-cleanup (optional, but good practice)
            # self.collection.create_index("timestamp", expireAfterSeconds=30*24*3600) 

    def save_message(self, user_id: str, room_id: str, role: str, content: str) -> str:
        """
        Save a new message.
        """
        msg_id = str(uuid.uuid4())
        
        if self.collection is None:
            logger.warning("DB not connected, skipping save.")
            return msg_id

        message = {
            "_id": msg_id,
            "user_id": user_id,
            "room_id": room_id,
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            "is_deleted": False
        }
        self.collection.insert_one(message)
        return msg_id

    def get_history(self, room_id: str, limit: int = 50, skip: int = 0) -> List[Dict]:
        """
        Get chat history for a room with pagination.
        """
        if self.collection is None:
            return []

        cursor = self.collection.find(
            {"room_id": room_id, "is_deleted": False}
        ).sort("timestamp", ASCENDING).skip(skip).limit(limit)
        
        return list(cursor)

    def get_user_rooms(self, user_id: str) -> List[Dict]:
        """
        Get list of chat rooms for a user, sorted by last activity.
        """
        if self.collection is None:
            return []

        pipeline = [
            {"$match": {"user_id": user_id, "is_deleted": False}},
            {"$sort": {"timestamp": ASCENDING}},  # Ensure we get the actual first message
            {"$group": {
                "_id": "$room_id",
                "last_message_at": {"$max": "$timestamp"},
                "first_message": {"$first": "$content"}
            }},
            {"$sort": {"last_message_at": DESCENDING}}
        ]
        
        return list(self.collection.aggregate(pipeline))

    def soft_delete_message(self, message_id: str) -> bool:
        """
        Soft delete a message by setting is_deleted=True.
        """
        if self.collection is None:
            return False

        result = self.collection.update_one(
            {"_id": message_id},
            {"$set": {"is_deleted": True}}
        )
        return result.modified_count > 0
