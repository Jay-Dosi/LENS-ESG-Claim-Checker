"""
Configuration management for ESG Claim Verification Assistant
Stateless architecture with ChromaDB - NO external storage required
"""
import os
from typing import Optional, Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Gemini Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-1.5-flash"
    
    # Storage Configuration - ChromaDB (Stateless)
    storage_mode: Literal["memory", "persistent"] = "memory"  # memory = stateless, persistent = local disk
    storage_persist_directory: str = "./chroma_storage"  # Only used if storage_mode = "persistent"
    session_timeout_minutes: int = 60  # Session timeout in minutes
    
    # NLU Configuration - Watson NLU is configured above
    
    # External APIs
    # OpenWeatherMap Air Pollution API (Optional - free tier: 1000 calls/day)
    openweathermap_api_key: Optional[str] = None
    
    # Application Settings
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    allowed_extensions: str = "pdf"
    log_level: str = "INFO"
    
    # CORS Settings
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Computed properties
    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size to bytes"""
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get list of allowed file extensions"""
        return [ext.strip() for ext in self.allowed_extensions.split(",")]
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def validate_storage_config(self) -> None:
        """Validate storage configuration"""
        if self.storage_mode == "persistent":
            if not os.path.exists(os.path.dirname(self.storage_persist_directory) or "."):
                os.makedirs(self.storage_persist_directory, exist_ok=True)
    
    def validate_llm_config(self) -> None:
        """Validate LLM configuration"""
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required")


# Global settings instance
settings = Settings()

# Validate configuration on startup
try:
    settings.validate_llm_config()
    settings.validate_storage_config()
except ValueError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Configuration validation warning: {e}")


def get_settings() -> Settings:
    """Dependency injection for FastAPI"""
    return settings

# Made with Bob
