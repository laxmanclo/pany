from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
import aiofiles
import os
import uuid
import asyncio
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager

# Import our models and services
from models import (
    EmbeddingRequest, EmbeddingResponse, SearchRequest, SearchResponse,
    SearchResult, HealthResponse, ErrorResponse
)
from services import embedding_service, db_service
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Pany Embedding Service...")
    
    try:
        # Initialize services
        await embedding_service.initialize()
        await db_service.initialize()
        logger.info("All services initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Pany Embedding Service...")

# Create FastAPI app
app = FastAPI(
    title="Pany - Open Source Semantic Search",
    description="Self-hosted semantic search engine with multi-modal support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly whenerv production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs_url": "/docs",
        "health_url": "/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if (embedding_service.is_ready() and db_service.is_ready()) else "unhealthy",
        version=settings.api_version,
        database_connected=db_service.is_ready(),
        model_loaded=embedding_service.is_ready(),
        timestamp=datetime.now()
    )

@app.post("/embeddings", response_model=EmbeddingResponse)
async def create_embedding(request: EmbeddingRequest):
    """Generate and store embedding for content"""
    try:
        start_time = time.time()
        
        # Validate modality
        if request.modality not in ["text", "image"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported modality: {request.modality}. Supported: text, image"
            )
        
        # Generate embedding
        embedding = await embedding_service.generate_embedding(
            request.content, 
            request.modality
        )
        
        # Store in database
        success = await db_service.store_embedding(
            request.content_id,
            request.modality,
            request.content,
            embedding,
            request.metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store embedding")
        
        end_time = time.time()
        logger.info(f"Created embedding for {request.content_id} in {(end_time - start_time)*1000:.2f}ms")
        
        return EmbeddingResponse(
            content_id=request.content_id,
            modality=request.modality,
            embedding=embedding,
            metadata=request.metadata,
            message="Embedding generated and stored successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=SearchResponse)
async def search_similar(request: SearchRequest):
    """Search for similar content using embeddings"""
    try:
        start_time = time.time()
        
        # Validate query modality
        if request.query_modality not in ["text", "image"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported query modality: {request.query_modality}"
            )
        
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(
            request.query,
            request.query_modality
        )
        
        # Search for similar embeddings
        results = await db_service.search_similar(
            query_embedding,
            request.target_modality,
            request.similarity_threshold,
            request.max_results
        )
        
        # Convert to SearchResult objects
        search_results = [
            SearchResult(
                content_id=result["content_id"],
                modality=result["modality"],
                content=result["content"],
                similarity=result["similarity"],
                metadata=result["metadata"]
            )
            for result in results
        ]
        
        end_time = time.time()
        execution_time = (end_time - start_time) * 1000
        
        logger.info(f"Search completed in {execution_time:.2f}ms, found {len(search_results)} results")
        
        return SearchResponse(
            query=request.query,
            query_modality=request.query_modality,
            results=search_results,
            total_results=len(search_results),
            execution_time_ms=execution_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...)
):
    """
    Simple file upload - just drop a file and it gets processed automatically
    """
    try:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'unknown'
        file_path = f"/tmp/{file_id}.{file_extension}"
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Process file and generate embeddings
        result = await embedding_service.process_uploaded_file(file_path, file_id, "default")
        
        # Store in database
        success = await db_service.store_embedding(
            result["content_id"],
            result["modality"],
            result.get("content", file.filename),
            result["embedding"],
            {
                "filename": file.filename,
                "file_size": len(content),
                "processing_time_ms": result["processing_time_ms"]
            }
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store file")
        
        # Clean up temp file
        os.unlink(file_path)
        
        return {
            "success": True,
            "content_id": result["content_id"],
            "message": f"File '{file.filename}' processed successfully",
            "modality": result["modality"],
            "processing_time_ms": result["processing_time_ms"]
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simple-search")
async def simple_search(
    query: str = Form(...),
    max_results: int = Form(10)
):
    """
    Simple search API: search across all uploaded content
    """
    try:
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(query, "text")
        
        # Search across all content
        results = await db_service.search_similar(
            query_embedding,
            similarity_threshold=0.5,
            max_results=max_results
        )
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/widget.js")
async def get_search_widget():
    """
    Returns the embeddable search widget JavaScript
    Usage: <script src="http://localhost:8000/widget.js"></script>
    """
    widget_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .pany-search-widget {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                max-width: 500px;
                margin: 20px 0;
            }}
            .pany-search-input {{
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
            }}            .pany-search-input:focus {{
                outline: none;
                border-color: #2563eb;
            }}
            .pany-results {{
                margin-top: 10px;
                max-height: 400px;
                overflow-y: auto;
            }}
            .pany-result-item {{
                padding: 10px;
                border: 1px solid #eee;
                border-radius: 6px;
                margin-bottom: 8px;
                cursor: pointer;
            }}
            .pany-result-item:hover {{
                background: #f5f5f5;
            }}
        </style>
    </head>
    <body>
        <div class="pany-search-widget">
            <input 
                type="text" 
                class="pany-search-input" 
                placeholder="Search your content..."
                id="pany-search-input"
            />
            <div id="pany-results" class="pany-results"></div>
        </div>
        
        <script>
            const searchInput = document.getElementById('pany-search-input');
            const resultsDiv = document.getElementById('pany-results');
            let searchTimeout;
            
            searchInput.addEventListener('input', function() {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {{
                    if (this.value.length > 2) {{
                        searchContent(this.value);
                    }} else {{
                        resultsDiv.innerHTML = '';
                    }}
                }}, 300);
            }});
            
            async function searchContent(query) {{
                try {{                    const formData = new FormData();
                    formData.append('query', query);
                    
                    const response = await fetch('/simple-search', {{
                        method: 'POST',
                        body: formData
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success && data.results.length > 0) {{
                        resultsDiv.innerHTML = data.results.map(result => `
                            <div class="pany-result-item" onclick="selectResult('${{result.content_id}}')">
                                <strong>${{result.content.substring(0, 100)}}...</strong>
                                <div style="font-size: 0.9em; color: #666;">
                                    ${{result.modality}} • ${{(result.similarity * 100).toFixed(1)}}% match
                                </div>
                            </div>
                        `).join('');
                    }} else {{
                        resultsDiv.innerHTML = '<div style="padding: 10px; color: #666;">No results found</div>';
                    }}
                }} catch (error) {{
                    console.error('Search error:', error);
                    resultsDiv.innerHTML = '<div style="padding: 10px; color: #red;">Search failed</div>';
                }}
            }}
            
            function selectResult(contentId) {{
                // Trigger custom event that parent page can listen to
                window.parent.postMessage({{
                    type: 'pany-result-selected',
                    contentId: contentId
                }}, '*');
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=widget_html)

@app.get("/widget-embed.js")
async def get_widget_script():
    """
    The embed script that creates the search widget
    Usage: <script src="http://localhost:8000/widget-embed.js"></script>
    """
    script = """
    (function() {
        // Create search widget dynamically
        const container = document.getElementById('pany-search');
        if (!container) {
            console.error('Pany Widget: Element with id "pany-search" not found');
            return;
        }
        
        container.innerHTML = `
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px;">
                <input 
                    type="text" 
                    id="pany-search-input"
                    placeholder="Search your content..."
                    style="width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px;"
                />
                <div id="pany-results" style="margin-top: 10px; max-height: 400px; overflow-y: auto;"></div>
            </div>
        `;
        
        const searchInput = document.getElementById('pany-search-input');
        const resultsDiv = document.getElementById('pany-results');
        let searchTimeout;
        
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (this.value.length > 2) {
                    searchContent(this.value);
                } else {
                    resultsDiv.innerHTML = '';
                }
            }, 300);
        });
        
        async function searchContent(query) {
            try {                const formData = new FormData();
                formData.append('query', query);
                
                const response = await fetch('/simple-search', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success && data.results.length > 0) {
                    resultsDiv.innerHTML = data.results.map(result => `
                        <div style="padding: 10px; border: 1px solid #eee; border-radius: 6px; margin-bottom: 8px; cursor: pointer;" onclick="selectResult('` + result.content_id + `')">
                            <strong>` + result.content.substring(0, 100) + `...</strong>
                            <div style="font-size: 0.9em; color: #666;">
                                ` + result.modality + ` • ` + (result.similarity * 100).toFixed(1) + `% match
                            </div>
                        </div>
                    `).join('');
                } else {
                    resultsDiv.innerHTML = '<div style="padding: 10px; color: #666;">No results found</div>';
                }
            } catch (error) {
                console.error('Search error:', error);
                resultsDiv.innerHTML = '<div style="padding: 10px; color: red;">Search failed</div>';
            }
        }
        
        window.selectResult = function(contentId) {
            const customEvent = new CustomEvent('panyResultSelected', {
                detail: { contentId: contentId }
            });
            document.dispatchEvent(customEvent);
        };
    })();
    """
    
    return Response(content=script, media_type="application/javascript")

@app.get("/stats", response_model=dict)
async def get_stats():
    """Get database statistics"""
    try:
        total_embeddings = await db_service.get_embedding_count()
        
        return {
            "total_embeddings": total_embeddings,
            "supported_modalities": ["text", "image"],
            "embedding_dimension": settings.embedding_dimension,
            "model": settings.clip_model_name
        }
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/demo", response_class=HTMLResponse)
async def get_demo():
    """Serve the e-commerce demo page"""
    demo_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pany E-commerce Search Demo</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            max-width: 1000px; margin: 0 auto; padding: 20px; 
            background: #f8fafc;
        }
        .header { text-align: center; margin-bottom: 30px; }
        .search-container { 
            background: white; padding: 25px; border-radius: 12px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 25px; 
        }
        .search-input { 
            width: 100%; padding: 15px; font-size: 16px; 
            border: 2px solid #e2e8f0; border-radius: 8px; 
            transition: border-color 0.2s;
        }
        .search-input:focus { outline: none; border-color: #2563eb; }
        .stats { 
            background: #eff6ff; padding: 12px 16px; border-radius: 6px; 
            margin-bottom: 20px; font-size: 14px; color: #1e40af;
        }
        .results { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .result-item { 
            padding: 20px; border-bottom: 1px solid #f1f5f9; 
            transition: background-color 0.2s;
        }
        .result-item:hover { background: #f8fafc; }
        .result-item:last-child { border-bottom: none; }
        .result-name { font-weight: 600; color: #1e293b; margin-bottom: 8px; }
        .result-description { color: #64748b; margin-bottom: 10px; }
        .result-meta { 
            display: flex; gap: 15px; font-size: 12px; color: #94a3b8; 
            align-items: center;
        }
        .similarity-badge { 
            background: #dbeafe; color: #1e40af; padding: 4px 8px; 
            border-radius: 4px; font-weight: 500;
        }
        .loading { text-align: center; padding: 40px; color: #64748b; }
        .example-queries {
            margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap;
        }
        .example-query {
            background: #f1f5f9; color: #475569; padding: 6px 12px; 
            border-radius: 20px; font-size: 12px; cursor: pointer;
            transition: background-color 0.2s;
        }
        .example-query:hover { background: #e2e8f0; }
        .success-message {
            background: #dcfce7; color: #166534; padding: 12px; border-radius: 6px;
            margin-bottom: 20px; text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Pany E-commerce Search</h1>
        <p>PostgreSQL-native semantic search with business intelligence</p>
        <div class="success-message">
            ✅ API Connected! Your semantic search is working.
        </div>
    </div>
    
    <div class="search-container">
        <input type="text" id="searchInput" class="search-input" 
               placeholder="Search for products... (e.g., 'red summer clothing', 'leather accessories')">
        
        <div class="example-queries">
            <span style="font-size: 12px; color: #64748b;">Try:</span>
            <div class="example-query" onclick="search('red clothing')">red clothing</div>
            <div class="example-query" onclick="search('leather accessories')">leather accessories</div>
            <div class="example-query" onclick="search('comfortable shoes')">comfortable shoes</div>
            <div class="example-query" onclick="search('summer dress')">summer dress</div>
        </div>
    </div>
    
    <div class="stats" id="stats">Ready to search...</div>
    
    <div id="results" class="results" style="display: none;">
        <!-- Results will appear here -->
    </div>
    
    <script>
        let searchTimeout;
        const searchInput = document.getElementById('searchInput');
        const resultsDiv = document.getElementById('results');
        const statsDiv = document.getElementById('stats');
        
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                if (this.value.length > 2) {
                    search(this.value);
                } else {
                    hideResults();
                }
            }, 500);
        });
        
        function hideResults() {
            resultsDiv.style.display = 'none';
            statsDiv.textContent = 'Ready to search...';
        }
        
        async function search(query) {
            try {
                searchInput.value = query;
                statsDiv.textContent = 'Searching...';
                resultsDiv.style.display = 'block';
                resultsDiv.innerHTML = '<div class="loading">🔍 Searching products...</div>';
                
                const startTime = Date.now();
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        query_modality: 'text',
                        max_results: 8
                    })
                });
                
                const endTime = Date.now();
                const data = await response.json();
                
                if (data.results && data.results.length > 0) {
                    displayResults(data.results);
                    statsDiv.innerHTML = `Found <strong>${data.results.length}</strong> products in <strong>${endTime - startTime}ms</strong> • <em>This is PostgreSQL-native semantic search!</em>`;
                } else {
                    resultsDiv.innerHTML = '<div class="loading">No products found. Try a different search term.</div>';
                    statsDiv.textContent = 'No results found';
                }
            } catch (error) {
                console.error('Search error:', error);
                resultsDiv.innerHTML = '<div class="loading">❌ Search failed: ' + error.message + '</div>';
                statsDiv.textContent = 'Search failed';
            }
        }
        
        function displayResults(results) {
            resultsDiv.innerHTML = results.map(result => {
                const similarity = Math.floor(result.similarity * 100);
                const metadata = result.metadata || {};
                const name = metadata.name || result.content.split(' - ')[0] || 'Product';
                const description = metadata.description || result.content.split(' - ')[1] || result.content;
                
                return `
                    <div class="result-item">
                        <div class="result-name">${name}</div>
                        <div class="result-description">${description}</div>
                        <div class="result-meta">
                            <span class="similarity-badge">${similarity}% match</span>
                            <span>Product ID: ${result.content_id}</span>
                            <span>Type: ${result.modality}</span>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Show a demo search after page loads
        setTimeout(() => {
            search('red summer');
        }, 1000);
    </script>
</body>
</html>'''
    return HTMLResponse(content=demo_html)

@app.post("/setup-demo")
async def setup_demo():
    """Setup demo data for e-commerce search"""
    products = [
        {"name": "Red Summer Dress", "description": "Flowing red dress perfect for summer occasions"},
        {"name": "Black Leather Boots", "description": "Genuine leather boots with sturdy sole"},
        {"name": "Blue Denim Jacket", "description": "Classic denim jacket in vintage blue"},
        {"name": "White Sneakers", "description": "Comfortable white sneakers for everyday wear"},
        {"name": "Green Backpack", "description": "Durable green backpack for outdoor adventures"},
        {"name": "Silver Watch", "description": "Elegant silver watch with leather strap"},
        {"name": "Pink Floral Blouse", "description": "Delicate pink blouse with floral patterns"},
        {"name": "Brown Leather Wallet", "description": "Classic brown leather wallet with multiple compartments"},
        {"name": "Navy Blue Jeans", "description": "Comfortable navy blue jeans with modern fit"},
        {"name": "Black Sunglasses", "description": "Stylish black sunglasses with UV protection"},
    ]
    
    success_count = 0
    errors = []
    
    for i, product in enumerate(products):
        try:
            content = f"{product['name']} - {product['description']}"
            
            # Generate embedding
            embedding = await embedding_service.generate_text_embedding(content)
            
            # Store in database
            success = await db_service.store_embedding(
                f"product_{i+1}",
                "text",
                content,
                embedding,
                {
                    "type": "product",
                    "name": product["name"],
                    "description": product["description"]
                }
            )
            
            if success:
                success_count += 1
            else:
                errors.append(f"Failed to store: {product['name']}")
                
        except Exception as e:
            errors.append(f"Error with {product['name']}: {str(e)}")
    
    return {
        "success": True,
        "message": f"Demo setup complete! {success_count}/{len(products)} products added.",
        "success_count": success_count,
        "total_products": len(products),
        "errors": errors
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.now()
        ).dict()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
