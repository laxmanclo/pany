-- Initialize the database with pgvector extension and tables

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table for multi-modal vectors
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL,
    modality VARCHAR(50) NOT NULL CHECK (modality IN ('text', 'image', 'audio', 'video')),
    content TEXT,  -- Original content (text) or file path (images)
    embedding vector(512),  -- CLIP embeddings are 512-dimensional
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient similarity search
CREATE INDEX IF NOT EXISTS idx_embeddings_content_id ON embeddings(content_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_modality ON embeddings(modality);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings(created_at);

-- HNSW index for vector similarity (pgvector's fastest index)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector_hnsw 
ON embeddings USING hnsw (embedding vector_cosine_ops);

-- Function to find similar content across modalities
CREATE OR REPLACE FUNCTION find_similar_multimodal(
    query_embedding vector(512),
    target_modality VARCHAR(50) DEFAULT NULL,
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    content_id VARCHAR(255),
    modality VARCHAR(50),
    content TEXT,
    similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.content_id,
        e.modality,
        e.content,
        1 - (e.embedding <=> query_embedding) AS similarity,
        e.metadata
    FROM embeddings e
    WHERE 
        (target_modality IS NULL OR e.modality = target_modality)
        AND (1 - (e.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;
