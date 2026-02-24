"""
Application configuration management using Pydantic Settings.
Loads environment variables and provides type-safe configuration.
"""
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    database_url_sync: str
    
    # Redis
    redis_url: str
    
    # API Keys
    openai_api_key: str
    deepgram_api_key: str
    elevenlabs_api_key: str
    
    # LangFuse
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str = "https://cloud.langfuse.com"
    
    # Security
    jwt_secret: str
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Application
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    max_concurrent_calls: int = 100
    enable_voice_auth: bool = False
    
    # Voice Pipeline
    deepgram_model: str = "nova-2"
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    elevenlabs_model: str = "eleven_turbo_v2"
    audio_sample_rate: int = 16000
    
    # Rate Limiting
    rate_limit_per_minute: int = 10
    max_sessions_per_ip: int = 3
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


# Global settings instance
settings = Settings()
