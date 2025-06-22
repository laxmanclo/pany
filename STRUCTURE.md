# 📁 Pany Repository Structure

## **Core Files**
```
pany/
├── README.md              # Main documentation
├── docker-compose.yml     # One-command deployment
├── start.bat / start.sh   # Quick start scripts
├── .env.example          # Environment configuration
│
├── embedding-service/     # Main application
│   ├── main.py           # FastAPI server
│   ├── config.py         # Configuration
│   ├── models.py         # Data models
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile        # Container setup
│   └── services/         # Core services
│       ├── embedding.py  # CLIP embeddings
│       └── database.py   # PostgreSQL operations
│
├── database/             # Database setup
│   └── init.sql         # PostgreSQL + pgvector schema
│
└── examples/            # Usage examples
    ├── simple_demo.py   # Basic API usage
    ├── test_api.py      # API testing
    └── web_demo.html    # Frontend example
```

## **What Each File Does**

### **🚀 Quick Start**
- `start.bat/sh` - One command to start everything
- `docker-compose.yml` - Container orchestration
- `.env.example` - Configuration template

### **🧠 Core Engine**
- `embedding-service/main.py` - FastAPI server with all endpoints
- `embedding-service/services/embedding.py` - CLIP model integration
- `embedding-service/services/database.py` - PostgreSQL operations

### **🗄️ Database**
- `database/init.sql` - Creates tables with pgvector support

### **📚 Examples**
- `examples/simple_demo.py` - Shows how simple the API is
- `examples/test_api.py` - Testing utilities
- `examples/web_demo.html` - Frontend integration example

## **Key Features Built-In**

### **API Endpoints**
- `GET /demo` - Live interactive demo
- `POST /setup-demo` - Populate sample data
- `POST /embeddings` - Store embeddings
- `POST /search` - Semantic search
- `GET /health` - System status
- `GET /stats` - Usage statistics

### **What Makes This Special**
1. **Everything in PostgreSQL** - No separate vector database
2. **Multi-modal ready** - Text and image embeddings
3. **SQL join capable** - Combine search with business data
4. **Docker deployment** - One command setup
5. **Cost effective** - $0/month vs $70+/month alternatives

This is a complete, production-ready semantic search engine that runs entirely in PostgreSQL.
