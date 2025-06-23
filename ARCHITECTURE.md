# Pany Architecture

## Overview

Pany runs semantic search directly inside PostgreSQL using the pgvector extension. This eliminates the need for separate vector databases and allows direct SQL joins with your business data.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT APPLICATIONS                      │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Web App       │   Mobile App    │   Direct SQL Access         │
│   (JavaScript)  │   (REST API)    │   (Business Intelligence)   │
└─────────────────┴─────────────────┴─────────────────────────────┘
                           │
                    ═══════════════
                           │
┌─────────────────────────────────────────────────────────────────┐
│                       PANY API LAYER                           │
├─────────────────────────────────────────────────────────────────┤
│  FastAPI Server (Python)                                       │
│  ├── File Upload & Processing                                  │
│  ├── CLIP Model (Text + Image Embeddings)                     │
│  ├── Search Endpoints                                          │
│  └── Web Interface                                             │
└─────────────────────────────────────────────────────────────────┘
                           │
                    ═══════════════
                           │
┌─────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL DATABASE                         │
├─────────────────────────────────────────────────────────────────┤
│  pgvector Extension                                             │
│  ├── Vector Storage (embeddings)                               │
│  ├── Similarity Search (cosine, L2, inner product)            │
│  └── Standard PostgreSQL Tables                                │
│                                                                 │
│  Your Business Data                                             │
│  ├── Products, Users, Orders, etc.                            │
│  ├── Metadata and Relations                                    │
│  └── Direct SQL Joins with Search Results                     │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Content Upload
```
File Upload → CLIP Model → Generate Embedding → Store in PostgreSQL
```

1. User uploads file (PDF, image, text) via API or web interface
2. File is processed and content extracted
3. CLIP model generates embedding vector (768 dimensions)
4. Embedding stored in PostgreSQL with metadata

### 2. Search Query
```
Query → CLIP Model → Generate Query Embedding → Vector Search → Results
```

1. User submits search query (text or image)
2. Query processed through same CLIP model
3. Vector similarity search in PostgreSQL using pgvector
4. Results ranked by similarity score
5. Joined with business data if needed

## Key Components

### CLIP Model
- **Purpose**: Multi-modal embeddings for text and images
- **Model**: OpenAI's CLIP (Contrastive Language-Image Pre-training)
- **Output**: 768-dimensional vectors
- **Capability**: Cross-modal search (text finds images, images find text)

### pgvector Extension
- **Vector Storage**: Efficient storage of high-dimensional vectors
- **Similarity Search**: Cosine similarity, L2 distance, inner product
- **Indexing**: HNSW and IVFFlat indexes for fast search
- **SQL Integration**: Native PostgreSQL functions for vector operations

### FastAPI Server
- **File Processing**: Handle uploads, extract content
- **Embedding Generation**: Interface with CLIP model
- **Search API**: RESTful endpoints for search operations
- **Web Interface**: Built-in UI for file management and search

## Database Schema

```sql
-- Embeddings table
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) UNIQUE,
    project_id VARCHAR(255),
    modality VARCHAR(50), -- 'text', 'image'
    content TEXT,
    file_path VARCHAR(500),
    embedding vector(768), -- pgvector type
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity search function
CREATE OR REPLACE FUNCTION semantic_search(
    query_text TEXT,
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INT DEFAULT 10
)
RETURNS TABLE (
    content_id VARCHAR,
    similarity_score FLOAT,
    content TEXT,
    metadata JSONB
);
```

## Deployment Options

### 1. pip install (Development)
```bash
pip install pany
pany
```

### 2. Docker (Production)
```bash
docker-compose up -d
```

### 3. Kubernetes (Scale)
```yaml
# Separate pods for API server and PostgreSQL
# Horizontal pod autoscaling for API layer
# Persistent volumes for database
```

## Performance Characteristics

### Vector Search Performance
- **Index Type**: HNSW (Hierarchical Navigable Small World)
- **Search Speed**: Sub-second for millions of vectors
- **Memory Usage**: ~4KB per 768-dimensional vector
- **Scaling**: Linear with database resources

### Throughput
- **Concurrent Searches**: 100+ requests/second
- **Upload Processing**: Depends on file size and model inference
- **Memory Requirements**: 4GB+ for CLIP model

### Storage Requirements
- **Embeddings**: ~1KB per document/image
- **Original Files**: Stored on filesystem or object storage
- **Metadata**: Minimal overhead in PostgreSQL

## Comparison with Traditional Vector DBs

### Traditional Architecture
```
App → Vector DB (Pinecone/Weaviate) → Get IDs → PostgreSQL → Business Logic → Response
```

**Problems:**
- Multiple database systems to maintain
- Data synchronization challenges
- Complex queries across systems
- Vendor lock-in and costs

### Pany Architecture
```
App → PostgreSQL (pgvector + business data) → Response
```

**Benefits:**
- Single database system
- Native SQL joins
- No data synchronization
- Standard PostgreSQL tooling
- Zero vendor lock-in

## Security Considerations

### Data Privacy
- All data stays in your PostgreSQL database
- No external API calls for search (only for embedding generation)
- Standard PostgreSQL security and access controls

### API Security
- Authentication and authorization configurable
- HTTPS/TLS encryption in production
- Rate limiting and input validation

### Model Security
- CLIP model runs locally
- No data sent to external services for inference
- Model files can be cached locally

## Monitoring and Observability

### Metrics
- Search latency and throughput
- Embedding generation time
- Database performance
- File upload success rates

### Logging
- API request logs
- Error tracking and debugging
- Performance profiling
- Database query logs

### Health Checks
- API endpoint health
- Database connectivity
- Model availability
- Disk space and memory usage
