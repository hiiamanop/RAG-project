import time
import uuid
from chat_database import ChatDatabase
import mongomock
from unittest.mock import patch

def benchmark_mongodb_operations(num_messages=1000):
    """
    Benchmark insert and read operations using Mongomock (simulation).
    In a real environment, provide a real URI.
    """
    print(f"Starting benchmark with {num_messages} messages...")
    
    # Setup DB (Mock for safety/demo, replace URI for real test)
    with patch('chat_database.MongoClient', new=mongomock.MongoClient):
        db = ChatDatabase(uri="mongodb://mock-uri")
        # Ensure indexes are created on the mock db
        db._create_indexes()

        # 1. Benchmark Writes
        start_time = time.time()
        for i in range(num_messages):
            db.save_message(
                user_id="user_bench",
                room_id="room_bench",
                role="user",
                content=f"Message {i}"
            )
        end_time = time.time()
        write_duration = end_time - start_time
        print(f"Write Performance: {num_messages / write_duration:.2f} ops/sec ({write_duration:.4f}s total)")

        # 2. Benchmark Reads (Pagination)
        start_time = time.time()
        # Simulate reading all pages
        page_size = 50
        pages = num_messages // page_size
        for i in range(pages):
            db.get_history("room_bench", limit=page_size, skip=i*page_size)
        end_time = time.time()
        read_duration = end_time - start_time
        print(f"Read Performance (Paged): {pages / read_duration:.2f} pages/sec ({read_duration:.4f}s total)")

        # 3. Benchmark Search (User ID)
        start_time = time.time()
        count = db.messages.count_documents({"user_id": "user_bench"})
        end_time = time.time()
        print(f"Count/Search Performance: {end_time - start_time:.6f}s (Found {count} docs)")

if __name__ == "__main__":
    benchmark_mongodb_operations()
