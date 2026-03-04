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
    
    # Paths (using absolute paths or relative to project root)
    CREDENTIALS_PATH: str = "credentials.json"
    TOKEN_PATH: str = "token.pickle"
    DOWNLOADS_DIR: str = "downloads"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
