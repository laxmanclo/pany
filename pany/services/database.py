import asyncio
import logging
import time
from typing import List, Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import asyncpg
from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseService:
    """Service for database operations with pgvector"""
    
    def __init__(self):
        self.engine = None
        self.async_session = None
        self.connection_pool = None
        self._is_ready = False
    
    async def initialize(self):
        """Initialize database connection"""
        try:
            # Create async engine for PostgreSQL
            database_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
            self.engine = create_async_engine(
                database_url,
                poolclass=NullPool,
                echo=False
            )
            
            # Create session factory
            self.async_session = sessionmaker(
                self.engine, 
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            await self.test_connection()
            self._is_ready = True
            logger.info("Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if database is ready"""
        return self._is_ready
    
    async def test_connection(self) -> bool:
        """Test database connection"""
        try:
            async with self.async_session() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    async def store_embedding(
        self, 
        content_id: str, 
        modality: str, 
        content: str, 
        embedding: List[float], 
        metadata: Dict[str, Any]
    ) -> bool:
        """Store embedding in the database"""
        try:
            async with self.async_session() as session:
                # Convert embedding list to string format for pgvector
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                
                # Insert or update embedding
                query = text("""
                    INSERT INTO embeddings (content_id, modality, content, embedding, metadata)
                    VALUES (:content_id, :modality, :content, :embedding, :metadata)
                    ON CONFLICT (content_id) 
                    DO UPDATE SET 
                        modality = :modality,
                        content = :content,
                        embedding = :embedding,
                        metadata = :metadata,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                await session.execute(query, {
                    "content_id": content_id,
                    "modality": modality,
                    "content": content,
                    "embedding": embedding_str,
                    "metadata": metadata
                })
                
                await session.commit()
                logger.info(f"Stored embedding for {content_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            return False
    
    async def search_similar(
        self,
        query_embedding: List[float],
        target_modality: Optional[str] = None,
        similarity_threshold: float = 0.7,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for similar embeddings"""
        try:
            async with self.async_session() as session:
                # Convert embedding to string format for pgvector
                embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"
                
                # Build query
                query = text("""
                    SELECT * FROM find_similar_multimodal(
                        :query_embedding::vector(512),
                        :target_modality,
                        :similarity_threshold,
                        :max_results
                    )
                """)
                
                result = await session.execute(query, {
                    "query_embedding": embedding_str,
                    "target_modality": target_modality,
                    "similarity_threshold": similarity_threshold,
                    "max_results": max_results
                })
                
                # Convert results to list of dictionaries
                results = []
                for row in result:
                    results.append({
                        "content_id": row.content_id,
                        "modality": row.modality,
                        "content": row.content,
                        "similarity": float(row.similarity),
                        "metadata": row.metadata or {}
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to search similar embeddings: {e}")
            return []
    
    async def get_embedding_count(self) -> int:
        """Get total number of embeddings in database"""
        try:
            async with self.async_session() as session:
                result = await session.execute(text("SELECT COUNT(*) FROM embeddings"))
                return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to get embedding count: {e}")
            return 0

# Global service instance
db_service = DatabaseService()
