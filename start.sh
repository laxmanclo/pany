#!/bin/bash

# Pany Multi-Modal Vector Database - Quick Start Script

echo "🚀 Starting Pany Multi-Modal Vector Database..."
echo "================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install docker-compose."
    exit 1
fi

echo "📦 Building and starting services..."
docker-compose up --build -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Wait for database to be ready
echo "🔍 Checking database connection..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if docker exec pany_postgres pg_isready -U pany_user -d pany_vectordb > /dev/null 2>&1; then
        echo "✅ Database is ready!"
        break
    fi
    
    if [ $attempt -eq $max_attempts ]; then
        echo "❌ Database failed to start after $max_attempts attempts"
        docker-compose logs database
        exit 1
    fi
    
    echo "   Attempt $attempt/$max_attempts - waiting..."
    sleep 2
    ((attempt++))
done

# Wait for embedding service to be ready
echo "🔍 Checking embedding service..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Embedding service is ready!"
        break
    fi
    
    if [ $attempt -eq $max_attempts ]; then
        echo "❌ Embedding service failed to start after $max_attempts attempts"
        docker-compose logs embedding-service
        exit 1
    fi
    
    echo "   Attempt $attempt/$max_attempts - waiting..."
    sleep 3
    ((attempt++))
done

echo ""
echo "🎉 Pany Multi-Modal Vector Database is ready!"
echo "================================================"
echo ""
echo "📊 Service Status:"
echo "   • Database: http://localhost:5432 (pany_vectordb)"
echo "   • API: http://localhost:8000"
echo "   • Documentation: http://localhost:8000/docs"
echo "   • Health Check: http://localhost:8000/health"
echo ""
echo "🧪 Quick Test:"
echo "   cd examples && python test_api.py"
echo ""
echo "📝 Manual Testing:"
echo "   # Create a text embedding"
echo "   curl -X POST http://localhost:8000/embeddings \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"content_id\": \"test1\", \"modality\": \"text\", \"content\": \"Hello world\", \"metadata\": {}}'"
echo ""
echo "   # Search for similar content"
echo "   curl -X POST http://localhost:8000/search \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"query\": \"Hello\", \"query_modality\": \"text\", \"max_results\": 5}'"
echo ""
echo "🛑 To stop:"
echo "   docker-compose down"
echo ""
echo "🗂️  Database Access:"
echo "   docker exec -it pany_postgres psql -U pany_user -d pany_vectordb"
echo ""
