# 🚀 Pany - Quick Start Guide

**Get semantic search running in PostgreSQL in under 5 minutes.**

## ⚡ Super Quick Start

```bash
# 1. Clone and start (one command!)
git clone https://github.com/your-org/pany.git
cd pany
docker-compose up -d

# 2. Setup demo data
curl -X POST http://localhost:8000/setup-demo

# 3. Try it out!
curl -X POST http://localhost:8000/simple-search -d "query=red dress" -d "max_results=5"
```

**That's it!** You now have semantic search running in PostgreSQL.


## 📝 Basic Usage Examples

### 1. Upload and Search Files

```bash
# Upload an image
curl -X POST http://localhost:8000/upload \
  -F "file=@photo.jpg"

# Upload a text document  
curl -X POST http://localhost:8000/upload \
  -F "file=@document.txt"

# Search across all uploads
curl -X POST http://localhost:8000/simple-search \
  -d "query=red summer clothing" \
  -d "max_results=10"
```

### 2. API Integration (Python)

```python
import requests

# Simple search
response = requests.post('http://localhost:8000/simple-search', data={
    'query': 'red summer dress',
    'max_results': 10
})
results = response.json()

# Upload file
with open('photo.jpg', 'rb') as f:
    response = requests.post('http://localhost:8000/upload', 
                           files={'file': f})
```

### 3. Advanced Search with Business Logic

```python
# This is the magic - semantic search + SQL joins!
search_request = {
    "query": "red summer dress",
    "query_modality": "text",
    "target_modality": "text",  # or "image" for cross-modal
    "similarity_threshold": 0.7,
    "max_results": 10
}

response = requests.post('http://localhost:8000/search', 
                        json=search_request)
```

### 4. Embed Search Widget

```html
<!-- Add this to any webpage -->
<div id="pany-search"></div>
<script src="http://localhost:8000/widget-embed.js"></script>

<script>
// Listen for search results
document.addEventListener('panyResultSelected', function(event) {
    console.log('Selected:', event.detail.contentId);
});
</script>
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Database (required)
DATABASE_URL=postgresql://pany_user:pany_password@localhost:5432/pany_vectordb

# Optional: OpenAI for comparison
OPENAI_API_KEY=your_openai_key_here

# Model settings
CLIP_MODEL_NAME=ViT-B/32
MAX_IMAGE_SIZE=5242880  # 5MB
EMBEDDING_DIMENSION=512
```

### Docker Compose Customization

```yaml
# docker-compose.override.yml
version: '3.8'
services:
  embedding-service:
    environment:
      - MAX_IMAGE_SIZE=10485760  # 10MB
    ports:
      - "8080:8000"  # Use different port
```

## 🎨 Web Interface

Visit http://localhost:8000/demo for a full e-commerce search demo.

**Available endpoints:**
- `/` - API info
- `/health` - Service status  
- `/docs` - Interactive API docs
- `/demo` - Web demo
- `/stats` - Database statistics

## 💾 Database Schema

Your embeddings are stored in PostgreSQL:

```sql
-- View all embeddings
SELECT content_id, modality, content, 
       (metadata->>'name') as name 
FROM embeddings;

-- Manual similarity search
SELECT content_id, content, 
       1 - (embedding <=> '[0.1,0.2,...]'::vector) as similarity
FROM embeddings 
ORDER BY similarity DESC 
LIMIT 10;
```

## 🐛 Troubleshooting

### Service won't start?
```bash
# Check logs
docker-compose logs embedding-service
docker-compose logs database

# Restart services
docker-compose restart
```

### Database connection issues?
```bash
# Test database directly
docker exec -it pany_postgres psql -U pany_user -d pany_vectordb -c "SELECT COUNT(*) FROM embeddings;"
```

### Model loading slowly?
The CLIP model downloads on first run. Subsequent starts are faster.

## 🔄 Production Deployment

### 1. Security First

```yaml
# docker-compose.prod.yml
services:
  embedding-service:
    environment:
      - CORS_ORIGINS=https://yoursite.com  # Lock down CORS
```

### 2. Scale Up

```yaml
services:
  embedding-service:
    deploy:
      replicas: 3  # Multiple instances
    environment:
      - MAX_BATCH_SIZE=64  # Larger batches
```

### 3. Monitor Performance

```bash
# Database stats
curl http://localhost:8000/stats

# Health check
curl http://localhost:8000/health
```

## 🎯 Real Business Example

```sql
-- This is IMPOSSIBLE with external vector databases
SELECT 
    p.product_name,
    p.price, 
    p.inventory_count,
    s.similarity_score,
    c.category_name
FROM products p
JOIN semantic_search('red summer dress', 0.8) s ON p.id = s.content_id
JOIN categories c ON p.category_id = c.id
WHERE p.in_stock = true 
  AND p.price BETWEEN 20 AND 100
  AND c.category_name = 'clothing'
ORDER BY s.similarity_score DESC, p.price ASC
LIMIT 10;
```

**This query combines:**
- Semantic similarity search
- Inventory management  
- Price filtering
- Category filtering
- Custom sorting logic

**All in one PostgreSQL query!**

---

**Questions?** Check `/docs` for full API reference or create an issue on GitHub.

**This is the future of semantic search - built on the database you already trust.**
