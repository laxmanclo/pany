-- Initialize the database with pgvector extension and tables

-- Create user and database (if running as postgres user)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'pany_user') THEN
        CREATE ROLE pany_user WITH LOGIN PASSWORD 'pany_password';
    END IF;
END
$$;

-- The database is created by docker-compose environment variables
GRANT ALL PRIVILEGES ON DATABASE pany_vectordb TO pany_user;

-- Connect to the new database
\c pany_vectordb

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table for multi-modal vectors with multi-tenant support
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
    modality VARCHAR(50) NOT NULL CHECK (modality IN ('text', 'image', 'audio', 'video')),
    content TEXT,  -- Original content (text) or file path (images)
    embedding vector(512),  -- CLIP embeddings are 512-dimensional
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for efficient similarity search and multi-tenancy
CREATE INDEX IF NOT EXISTS idx_embeddings_content_id ON embeddings(content_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_tenant_id ON embeddings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_modality ON embeddings(modality);
CREATE INDEX IF NOT EXISTS idx_embeddings_created_at ON embeddings(created_at);
CREATE INDEX IF NOT EXISTS idx_embeddings_tenant_modality ON embeddings(tenant_id, modality);

-- HNSW index for vector similarity (pgvector's fastest index)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector_hnsw 
ON embeddings USING hnsw (embedding vector_cosine_ops);

-- Unique constraint for tenant-scoped content
CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_tenant_content 
ON embeddings(tenant_id, content_id);

-- Function to find similar content across modalities with tenant isolation
CREATE OR REPLACE FUNCTION find_similar_multimodal(
    query_embedding vector(512),
    target_tenant_id VARCHAR(100) DEFAULT NULL,
    target_modality VARCHAR(50) DEFAULT NULL,    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    content_id VARCHAR(255),
    tenant_id VARCHAR(100),
    modality VARCHAR(50),
    content TEXT,
    similarity FLOAT,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.content_id,
        e.tenant_id,
        e.modality,
        e.content,
        1 - (e.embedding <=> query_embedding) AS similarity,
        e.metadata
    FROM embeddings e
    WHERE 
        (target_tenant_id IS NULL OR e.tenant_id = target_tenant_id)
        AND (target_modality IS NULL OR e.modality = target_modality)
        AND (1 - (e.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- RAG-ready function for context retrieval
CREATE OR REPLACE FUNCTION get_rag_context(
    query_embedding vector(512),
    target_tenant_id VARCHAR(100),
    context_size INTEGER DEFAULT 5,
    similarity_threshold FLOAT DEFAULT 0.6
)
RETURNS TEXT AS $$
DECLARE
    context_text TEXT := '';
    record_row RECORD;
BEGIN
    FOR record_row IN
        SELECT content, (1 - (embedding <=> query_embedding)) as similarity
        FROM embeddings 
        WHERE tenant_id = target_tenant_id
          AND modality = 'text'
          AND (1 - (embedding <=> query_embedding)) >= similarity_threshold
        ORDER BY embedding <=> query_embedding
        LIMIT context_size
    LOOP
        context_text := context_text || record_row.content || '\n\n---\n\n';
    END LOOP;
    
    RETURN context_text;
END;
$$ LANGUAGE plpgsql;

-- Connect as pany_user for proper permissions
\c pany_vectordb pany_user

-- Grant permissions to pany_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pany_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pany_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO pany_user;
