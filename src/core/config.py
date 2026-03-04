from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "GDrive Chatbot"
    DEBUG: bool = False
    
    # Google API
    GOOGLE_API_KEY: str
    
    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "gdrive_chatbot"
    
    # Paths (using absolute paths or relative to project root)# Paths
    CREDENTIALS_PATH: str = "credentials.json"
    TOKEN_PATH: str = "token.pickle"
    DOWNLOADS_DIR: str = "downloads"
    
    # Search & Agent Config
    SEARCH_API_PROVIDER: str = "duckduckgo" # Options: duckduckgo, serpapi, bing
    SERPAPI_API_KEY: Optional[str] = None
    BING_SEARCH_API_KEY: Optional[str] = None
    LLM_CONFIDENCE_THRESHOLD: float = 0.7
    MAX_SEARCH_RESULTS: int = 3
    CACHE_TTL: int = 3600

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
