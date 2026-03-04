import pytest
from unittest.mock import MagicMock, patch
from chat_database import ChatDatabase
from datetime import datetime, timedelta, timezone
import mongomock

@pytest.fixture
def mock_db():
    with patch('chat_database.MongoClient', new=mongomock.MongoClient):
        # The uri doesn't matter for mongomock, but we pass one to trigger the connection logic
        db = ChatDatabase(uri="mongodb://localhost")
        return db

def test_save_message(mock_db):
    msg_id = mock_db.save_message("user1", "room1", "user", "Hello")
    assert msg_id is not None
    
    doc = mock_db.messages.find_one({"_id": msg_id})
    assert doc["content"] == "Hello"
    assert doc["user_id"] == "user1"
    assert doc["is_deleted"] is False

def test_get_history(mock_db):
    mock_db.save_message("user1", "room1", "user", "Hi 1")
    # Small delay to ensure timestamp order
    import time
    time.sleep(0.001)
    mock_db.save_message("user1", "room1", "assistant", "Hello 1")
    
    history = mock_db.get_history("room1")
    assert len(history) == 2
    assert history[0]["content"] == "Hi 1"
    assert history[1]["content"] == "Hello 1"

def test_soft_delete(mock_db):
    msg_id = mock_db.save_message("user1", "room1", "user", "To be deleted")
    success = mock_db.soft_delete_message(msg_id)
    assert success is True
    
    doc = mock_db.messages.find_one({"_id": msg_id})
    assert doc["is_deleted"] is True
    
    # Should not appear in history
    history = mock_db.get_history("room1")
    assert len(history) == 0

def test_retention_policy(mock_db):
    # Insert old message
    old_date = datetime.now(timezone.utc) - timedelta(days=31)
    mock_db.messages.insert_one({
        "_id": "old_msg",
        "timestamp": old_date,
        "content": "Old",
        "is_deleted": False
    })
    
    # Insert new message
    mock_db.save_message("user1", "room1", "user", "New")
    
    deleted_count = mock_db.enforce_retention_policy(days=30)
    assert deleted_count == 1
    
    remaining = list(mock_db.messages.find())
    assert len(remaining) == 1
    assert remaining[0]["content"] == "New"
