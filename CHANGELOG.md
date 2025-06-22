# Changelog

All notable changes to Pany will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-06-22

### Added
- PostgreSQL-native semantic search engine
- Multi-modal embeddings using CLIP (text + images)
- FastAPI backend with async/await
- Docker Compose deployment
- Interactive demo at `/demo`
- Embeddable search widget
- RESTful API with OpenAPI documentation
- Sample data setup endpoint
- Health check and statistics endpoints

### Features
- **PostgreSQL Integration**: Runs entirely in PostgreSQL using pgvector
- **Multi-modal Search**: Text and image embeddings in unified space
- **SQL Joins**: Combine semantic search with business data
- **Cost Effective**: $0/month self-hosted alternative to vector databases
- **Developer Friendly**: 10-minute Docker setup

### Technical
- CLIP ViT-B/32 model for embeddings
- PostgreSQL + pgvector for vector storage
- FastAPI for async API server
- Docker containerization
- CORS support for web integration

## [0.1.0] - 2025-06-20

### Added
- Initial project structure
- Basic embedding generation
- Database schema setup
