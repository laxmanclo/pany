import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration settings"""
    
    # Database
    database_url: str = "postgresql://pany_user:pany_password@localhost:5432/pany_vectordb"
    
    # API Configuration
    api_title: str = "Pany Multi-Modal Vector Database"
    api_description: str = "A PostgreSQL extension for multi-modal vector search"
    api_version: str = "1.0.0"
    
    # Model Configuration
    clip_model_name: str = "ViT-B/32"  # Lightweight CLIP model
    max_image_size: int = 1024 * 1024 * 5  # 5MB max image size
    supported_image_types: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    
    # Cache Configuration
    model_cache_dir: str = "/app/cache"
    
    # Optional: OpenAI Configuration
    openai_api_key: Optional[str] = None
    
    # Performance
    max_batch_size: int = 32
    embedding_dimension: int = 512  # CLIP ViT-B/32 embedding size
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
