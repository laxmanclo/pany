from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class EmbeddingRequest(BaseModel):
    """Request model for generating embeddings"""
    model_config = ConfigDict(protected_namespaces=())
    
    content_id: str = Field(..., description="Unique identifier for the content")
    modality: str = Field(..., description="Type of content: text, image, audio, video")
    content: str = Field(..., description="Text content or base64 encoded image")
    metadata: Optional[dict] = Field(default={}, description="Additional metadata")

class EmbeddingResponse(BaseModel):
    """Response model for embedding generation"""
    model_config = ConfigDict(protected_namespaces=())
    
    content_id: str
    modality: str
    embedding: List[float]
    metadata: dict
    message: str = "Embedding generated successfully"

class SearchRequest(BaseModel):
    """Request model for similarity search"""
    model_config = ConfigDict(protected_namespaces=())
    
    query: str = Field(..., description="Text query or base64 encoded image")
    query_modality: str = Field(..., description="Modality of the query: text or image")
    target_modality: Optional[str] = Field(None, description="Filter results by modality")
    similarity_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity score")
    max_results: int = Field(10, ge=1, le=100, description="Maximum number of results")

class SearchResult(BaseModel):
    """Individual search result"""
    model_config = ConfigDict(protected_namespaces=())
    
    content_id: str
    modality: str
    content: str
    similarity: float
    metadata: dict

class SearchResponse(BaseModel):
    """Response model for similarity search"""
    model_config = ConfigDict(protected_namespaces=())
    
    query: str
    query_modality: str
    results: List[SearchResult]
    total_results: int
    execution_time_ms: float

class HealthResponse(BaseModel):
    """Health check response"""
    model_config = ConfigDict(protected_namespaces=())
    
    status: str
    version: str
    database_connected: bool
    ml_model_loaded: bool  # Renamed from model_loaded to avoid namespace conflict
    timestamp: datetime

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: str
    timestamp: datetime
