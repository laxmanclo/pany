# Multi-Modal Vector Database

> **Status: Early Development** 🚧  
> This is a work-in-progress PostgreSQL extension for multi-modal vector search. Expect bugs, breaking changes, and incomplete features.

## What is this?

A PostgreSQL extension that lets you search across text, images, audio, and video using vector embeddings - all without leaving your existing PostgreSQL database.

**Why build another vector database?**
- Pinecone costs $70+/month for basic usage
- Most vector DBs require learning new APIs and managing separate infrastructure
- Multi-modal search usually means juggling multiple services
- Your data is already in PostgreSQL anyway

## Quick Example

```sql
-- Store multi-modal embeddings
INSERT INTO embeddings (content_id, modality, embedding, metadata) 
VALUES 
  ('doc1', 'text', '[0.1, 0.2, 0.3, ...]', '{"title": "My Document"}'),
  ('img1', 'image', '[0.4, 0.5, 0.6, ...]', '{"filename": "photo.jpg"}');

-- Find similar content across modalities
SELECT content_id, modality, metadata, 
       embedding <=> query_vector AS similarity
FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 10;

-- Multi-modal search: find images similar to text
SELECT * FROM find_similar_multimodal('A sunset over mountains', 'image', 5);
```

## Current Status

- [x] Basic PostgreSQL extension skeleton
- [x] Custom vector data type
- [ ] HNSW/IVF indexing (in progress)
- [ ] FAISS integration
- [ ] Multi-modal embedding service
- [ ] Production-ready features

**This is not ready for production use.**

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Embedding      │    │   FAISS         │
│   Extension     │◄──►│   Service        │    │   Service       │
│                 │    │                  │    │                 │
│ • Vector storage│    │ • Text→Vector    │    │ • Fast ANN      │
│ • SQL interface │    │ • Image→Vector   │    │ • Index mgmt    │
│ • Metadata      │    │ • Audio→Vector   │    │ • Persistence   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Installation

**Prerequisites:**
- PostgreSQL 15+ 
- Docker & Docker Compose
- Python 3.9+
- Build tools (gcc, make, postgresql-server-dev)

```bash
# Clone the repo
git clone https://github.com/yourusername/multimodal-vector-db.git
cd multimodal-vector-db

# Start all services
docker-compose up -d

# Install the PostgreSQL extension
make install
```

## Supported Modalities

| Modality | Status | Model |
|----------|--------|-------|
| Text | ✅ | OpenAI CLIP |
| Images | ✅ | OpenAI CLIP |
| Audio | 🔄 | Planned |
| Video | 🔄 | Planned |

## Performance

*Benchmarks coming soon. Current focus is on correctness, not speed.*

## Why PostgreSQL?

- **Familiar**: You already know SQL
- **Reliable**: ACID transactions, backups, replication
- **Integrated**: Your data, metadata, and vectors in one place
- **Cost-effective**: No separate vector DB hosting costs
- **Flexible**: Join vectors with your existing tables

## Roadmap

**Phase 1 (Current):** Core functionality
- PostgreSQL extension with basic vector operations
- Simple multi-modal embedding service
- FAISS integration for performance

**Phase 2:** Production readiness
- Performance optimizations
- Horizontal scaling
- Advanced indexing strategies

**Phase 3:** Advanced features
- Real-time vector updates
- Custom embedding models
- Vector compression

## Contributing

This is an early-stage project. If you're interested in contributing:

1. **Try it out** and report bugs
2. **Suggest use cases** you'd actually use this for
3. **Contribute code** (see CONTRIBUTING.md)

**What we need help with:**
- PostgreSQL C extension expertise
- Multi-modal ML model integration
- Performance optimization
- Documentation and examples

## FAQ

**Q: How is this different from pgvector?**
A: pgvector is single-modal and requires you to generate embeddings elsewhere. This handles multi-modal embeddings end-to-end.

**Q: Can I use this in production?**
A: Not yet. This is alpha software. Use at your own risk.

**Q: What about licensing?**
A: MIT license. Use it however you want.

**Q: Will this scale?**
A: The goal is to handle millions of vectors efficiently. We're not there yet.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This project is experimental. It may eat your data, crash your database, or summon eldritch horrors. Use responsibly.

---

*Built with ☕ and questionable life choices*