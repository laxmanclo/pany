"""
Test suite for Pany
"""

import pytest
import asyncio
from pany.services.embedding import EmbeddingService
from pany.services.database import DatabaseService


@pytest.mark.asyncio
async def test_embedding_service():
    """Test embedding service initialization"""
    service = EmbeddingService()
    await service.initialize()
    
    # Test text embedding
    text = "red summer dress"
    embedding = await service.generate_text_embedding(text)
    
    assert isinstance(embedding, list)
    assert len(embedding) == 512  # CLIP ViT-B/32 dimension
    assert all(isinstance(x, float) for x in embedding)


def test_health_endpoint():
    """Test API health endpoint"""
    from fastapi.testclient import TestClient
    from pany.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_api_root():
    """Test API root endpoint"""
    from fastapi.testclient import TestClient
    from pany.main import app
    
    client = TestClient(app)
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


if __name__ == "__main__":
    pytest.main([__file__])
