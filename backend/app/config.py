"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import json
from pathlib import Path
from dotenv import load_dotenv


# Ensure root .env is loaded for any module that relies on environment variables
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS (parse JSON string from env)
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Database
    MONGO_USER: str = ""
    MONGO_PASS: str = ""
    MONGO_CLUSTER_URL: str = "localhost:27017"
    DATABASE_NAME: str = "smartshopper"
    
    # External APIs
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    TAVILY_API_KEY: str = ""
    
    # Tavily Configuration Override
    # Options: "development", "production", "auto" (uses ENVIRONMENT setting)
    # Cost comparison:
    # - development: search_depth="basic", max_results=6, fallback_max_depth=1 (cheaper)
    # - production: search_depth="advanced", max_results=12, fallback_max_depth=2 (expensive)
    TAVILY_CONFIG: str = "auto"
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    GOOGLE_ALLOWED_DOMAINS: List[str] = []
    GOOGLE_REQUIRE_VERIFIED_EMAIL: bool = True
    GOOGLE_OAUTH_SCOPES: List[str] = ["openid", "email", "profile"]

    # Auth
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    
    # Embeddings
    EMBEDDINGS_PROVIDER: str = "openai"  # "openai" or "minilm"
    
    # Email
    EMAIL_PROVIDER: str = "console"  # "ses", "sendgrid", "console"

    # RSS ingestion
    ENABLE_RSS_INGESTION: bool = True
    RSS_DEFAULT_POLL_MINUTES: int = 10
    RSS_MAX_CONCURRENT_FETCHES: int = 3
    RSS_EMBED_BATCH_SIZE: int = 16
    
    # Enhanced RSS price extraction
    TAVILY_RSS_FEED_INGESTION: bool = False  # Use Tavily for RSS link price extraction
    RSS_ENABLE_WEB_SCRAPING: bool = True     # Enable lightweight web scraping for prices
    RSS_SCRAPING_TIMEOUT: int = 5            # Timeout for web scraping in seconds
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse CORS_ORIGINS if it's a JSON string
        if isinstance(self.CORS_ORIGINS, str):
            try:
                self.CORS_ORIGINS = json.loads(self.CORS_ORIGINS)
            except json.JSONDecodeError:
                # Fallback to default if JSON parsing fails
                self.CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]
        
        if isinstance(self.GOOGLE_ALLOWED_DOMAINS, str):
            try:
                parsed = json.loads(self.GOOGLE_ALLOWED_DOMAINS)
                if isinstance(parsed, list):
                    self.GOOGLE_ALLOWED_DOMAINS = [str(domain) for domain in parsed]
                else:
                    self.GOOGLE_ALLOWED_DOMAINS = [domain.strip() for domain in self.GOOGLE_ALLOWED_DOMAINS.split(",") if domain.strip()]
            except json.JSONDecodeError:
                self.GOOGLE_ALLOWED_DOMAINS = [domain.strip() for domain in self.GOOGLE_ALLOWED_DOMAINS.split(",") if domain.strip()]

        if isinstance(self.GOOGLE_OAUTH_SCOPES, str):
            try:
                parsed = json.loads(self.GOOGLE_OAUTH_SCOPES)
                if isinstance(parsed, list):
                    self.GOOGLE_OAUTH_SCOPES = [str(scope) for scope in parsed]
                else:
                    self.GOOGLE_OAUTH_SCOPES = [scope.strip() for scope in self.GOOGLE_OAUTH_SCOPES.split(" ") if scope.strip()]
            except json.JSONDecodeError:
                separators = [",", " "]
                scopes: List[str] = []
                value = self.GOOGLE_OAUTH_SCOPES
                for separator in separators:
                    if separator in value:
                        scopes.extend([scope.strip() for scope in value.split(separator) if scope.strip()])
                        break
                if not scopes:
                    scopes = [value.strip()] if value.strip() else []
                self.GOOGLE_OAUTH_SCOPES = scopes
    
    @property 
    def mongodb_url(self) -> str:
        """Build MongoDB connection string optimized for AWS EB compatibility"""
        if self.MONGO_USER and self.MONGO_PASS:
            # Atlas format with minimal connection parameters - SSL handled in client
            return f"mongodb+srv://{self.MONGO_USER}:{self.MONGO_PASS}@{self.MONGO_CLUSTER_URL}/?retryWrites=true&w=majority&authSource=admin"
        else:
            # Local format: mongodb://localhost:27017/
            return f"mongodb://{self.MONGO_CLUSTER_URL}/"

    @property
    def google_client_ids(self) -> List[str]:
        """Return list of configured Google OAuth client IDs"""
        if not self.GOOGLE_CLIENT_ID:
            return []
        return [client_id.strip() for client_id in self.GOOGLE_CLIENT_ID.split(",") if client_id.strip()]


settings = Settings()
