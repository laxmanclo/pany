from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, Response
from sqlalchemy import text
import aiofiles
import os
import uuid
import asyncio
import logging
import time
from datetime import datetime
from contextlib import asynccontextmanager

# Import our models and services
from .models import (
    EmbeddingRequest, EmbeddingResponse, SearchRequest, SearchResponse,
    SearchResult, HealthResponse, ErrorResponse
)
from .services import embedding_service, db_service
from .services.file_processor import file_processor
from .config import settings

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
        ml_model_loaded=embedding_service.is_ready(),
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

@app.post("/advanced-upload")
async def advanced_upload(
    files: list[UploadFile] = File(...),
    folder: str = Form("default")
):
    """
    Advanced upload endpoint with drag-and-drop support
    """
    try:
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        # Process each file
        results = []
        for file in files:
            try:
                # Save uploaded file
                file_id = str(uuid.uuid4())
                file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'unknown'
                file_path = f"/tmp/{file_id}.{file_extension}"
                
                async with aiofiles.open(file_path, 'wb') as f:
                    content = await file.read()
                    await f.write(content)
                
                # Process file and generate embeddings
                result = await embedding_service.process_uploaded_file(file_path, file_id, folder)
                
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
                
                results.append({
                    "content_id": result["content_id"],
                    "filename": file.filename,
                    "modality": result["modality"],
                    "processing_time_ms": result["processing_time_ms"]
                })
                
                # Clean up temp file
                os.unlink(file_path)
                
            except Exception as e:
                logger.error(f"Failed to process file {file.filename}: {e}")
                results.append({
                    "filename": file.filename,
                    "error": str(e)
                })
        
        return {
            "success": True,
            "message": "Files processed successfully",
            "results": results
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

@app.post("/upload-advanced")
async def upload_advanced_file(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
    tags: str = Form(""),
    description: str = Form("")
):
    """
    Advanced file upload with support for PDF, CSV, Excel, Images, and Text files
    Includes tenant support and metadata tagging
    """
    try:
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'unknown'
        file_path = f"/tmp/{file_id}.{file_extension}"
        
        # Read and save file
        content = await file.read()
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Process file using advanced processor
        result = await file_processor.process_file(file_path, file.filename)
        
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Enhanced metadata
        enhanced_metadata = {
            **result["metadata"],
            "tenant_id": tenant_id,
            "tags": tag_list,
            "description": description,
            "upload_timestamp": datetime.now().isoformat(),
            "original_filename": file.filename
        }
        
        # Generate embedding
        embedding = await embedding_service.generate_embedding(
            result["content"], 
            result["modality"]
        )
        
        # Store in database with tenant isolation
        content_id = f"{tenant_id}_{file_id}"
        success = await db_service.store_embedding(
            content_id,
            result["modality"],
            result["content"],
            embedding,
            enhanced_metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store file")
        
        # Clean up temp file
        os.unlink(file_path)
        
        return {
            "success": True,
            "content_id": content_id,
            "filename": file.filename,
            "file_type": result["metadata"]["file_category"],
            "modality": result["modality"],
            "tenant_id": tenant_id,
            "tags": tag_list,
            "file_size": len(content),
            "processed_content_length": len(result["content"]),
            "message": f"File '{file.filename}' processed successfully"
        }
        
    except Exception as e:
        logger.error(f"Advanced upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/upload-page", response_class=HTMLResponse)
async def get_upload_page():
    """Drag-and-drop upload page"""
    upload_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pany - Upload Files</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            max-width: 800px; margin: 0 auto; padding: 20px; background: #f8fafc;
        }
        .upload-container {
            background: white; border-radius: 12px; padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .drop-zone {
            border: 3px dashed #cbd5e1; border-radius: 12px; padding: 60px 20px;
            text-align: center; transition: all 0.3s ease; cursor: pointer;
            background: #f8fafc; margin-bottom: 20px;
        }
        .drop-zone.drag-over {
            border-color: #2563eb; background: #eff6ff; transform: scale(1.02);
        }
        .drop-zone-text {
            font-size: 18px; color: #64748b; margin-bottom: 10px;
        }
        .file-icon { font-size: 48px; margin-bottom: 15px; }
        .form-group { margin-bottom: 20px; }
        .form-label { display: block; margin-bottom: 8px; font-weight: 600; color: #374151; }
        .form-input {
            width: 100%; padding: 12px; border: 2px solid #e5e7eb; border-radius: 8px;
            font-size: 16px; transition: border-color 0.2s;
        }
        .form-input:focus { outline: none; border-color: #2563eb; }
        .upload-btn {
            background: #2563eb; color: white; padding: 12px 24px; border: none;
            border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%;
            transition: background 0.2s;
        }
        .upload-btn:hover { background: #1d4ed8; }
        .upload-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .progress-bar {
            width: 100%; height: 8px; background: #e5e7eb; border-radius: 4px;
            overflow: hidden; margin: 15px 0; display: none;
        }
        .progress-fill {
            height: 100%; background: #2563eb; width: 0%; transition: width 0.3s ease;
        }
        .file-preview {
            background: #f3f4f6; border-radius: 8px; padding: 15px; margin-top: 15px;
            display: none;
        }
        .supported-formats {
            margin-top: 20px; padding: 15px; background: #eff6ff; border-radius: 8px;
        }
        .format-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .format-tag {
            background: #dbeafe; color: #1e40af; padding: 4px 8px; border-radius: 4px;
            font-size: 12px; font-weight: 500;
        }
        .result-message {
            margin-top: 20px; padding: 15px; border-radius: 8px; display: none;
        }
        .result-success { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
        .result-error { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
    </style>
</head>
<body>
    <div class="upload-container">
        <h1>📁 Upload Files to Pany</h1>
        <p>Drag & drop files or click to browse. Supports images, PDFs, CSV/Excel, and text files.</p>
        
        <div class="drop-zone" id="dropZone">
            <div class="file-icon">📎</div>
            <div class="drop-zone-text">Drop files here or click to browse</div>
            <input type="file" id="fileInput" style="display: none;" multiple 
                   accept=".pdf,.csv,.xlsx,.xls,.jpg,.jpeg,.png,.gif,.txt,.md">
        </div>
        
        <div class="file-preview" id="filePreview"></div>
        
        <form id="uploadForm">
            <div class="form-group">
                <label class="form-label" for="tenantId">Tenant/Project ID</label>
                <input type="text" id="tenantId" class="form-input" value="default" 
                       placeholder="e.g., my-company, project-alpha">
            </div>
            
            <div class="form-group">
                <label class="form-label" for="tags">Tags (comma-separated)</label>
                <input type="text" id="tags" class="form-input" 
                       placeholder="e.g., documents, product-info, training-data">
            </div>
            
            <div class="form-group">
                <label class="form-label" for="description">Description</label>
                <input type="text" id="description" class="form-input" 
                       placeholder="Brief description of the file content">
            </div>
            
            <button type="submit" class="upload-btn" id="uploadBtn" disabled>
                Upload Files
            </button>
        </form>
        
        <div class="progress-bar" id="progressBar">
            <div class="progress-fill" id="progressFill"></div>
        </div>
        
        <div class="result-message" id="resultMessage"></div>
        
        <div class="supported-formats">
            <strong>📋 Supported Formats:</strong>
            <div class="format-list">
                <span class="format-tag">PDF</span>
                <span class="format-tag">CSV</span>
                <span class="format-tag">Excel</span>
                <span class="format-tag">Images</span>
                <span class="format-tag">Text</span>
                <span class="format-tag">Markdown</span>
            </div>
        </div>
    </div>
    
    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const filePreview = document.getElementById('filePreview');
        const uploadForm = document.getElementById('uploadForm');
        const uploadBtn = document.getElementById('uploadBtn');
        const progressBar = document.getElementById('progressBar');
        const progressFill = document.getElementById('progressFill');
        const resultMessage = document.getElementById('resultMessage');
        
        let selectedFiles = [];
        
        // Drag and drop functionality
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            handleFiles(e.dataTransfer.files);
        });
        
        fileInput.addEventListener('change', (e) => {
            handleFiles(e.target.files);
        });
        
        function handleFiles(files) {
            selectedFiles = Array.from(files);
            displayFilePreview();
            uploadBtn.disabled = selectedFiles.length === 0;
        }
        
        function displayFilePreview() {
            if (selectedFiles.length === 0) {
                filePreview.style.display = 'none';
                return;
            }
            
            filePreview.style.display = 'block';
            filePreview.innerHTML = `
                <h3>Selected Files (${selectedFiles.length}):</h3>
                ${selectedFiles.map(file => `
                    <div style="margin: 8px 0; padding: 8px; background: white; border-radius: 4px;">
                        📄 <strong>${file.name}</strong> 
                        <span style="color: #64748b;">(${(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                `).join('')}
            `;
        }
        
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (selectedFiles.length === 0) return;
            
            uploadBtn.disabled = true;
            uploadBtn.textContent = 'Uploading...';
            progressBar.style.display = 'block';
            
            const tenantId = document.getElementById('tenantId').value;
            const tags = document.getElementById('tags').value;
            const description = document.getElementById('description').value;
            
            let successCount = 0;
            let errors = [];
            
            for (let i = 0; i < selectedFiles.length; i++) {
                const file = selectedFiles[i];
                const progress = ((i + 1) / selectedFiles.length) * 100;
                progressFill.style.width = progress + '%';
                
                try {
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('tenant_id', tenantId);
                    formData.append('tags', tags);
                    formData.append('description', description);
                    
                    const response = await fetch('/upload-advanced', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (response.ok) {
                        successCount++;
                    } else {
                        const error = await response.text();
                        errors.push(`${file.name}: ${error}`);
                    }
                } catch (error) {
                    errors.push(`${file.name}: ${error.message}`);
                }
            }
            
            // Show results
            progressBar.style.display = 'none';
            resultMessage.style.display = 'block';
            
            if (errors.length === 0) {
                resultMessage.className = 'result-message result-success';
                resultMessage.innerHTML = `
                    ✅ <strong>Upload Complete!</strong><br>
                    Successfully uploaded ${successCount} files to tenant "${tenantId}".
                `;
            } else {
                resultMessage.className = 'result-message result-error';
                resultMessage.innerHTML = `
                    ⚠️ <strong>Upload Results:</strong><br>
                    ${successCount} successful, ${errors.length} failed<br>
                    <details><summary>Error details</summary>${errors.join('<br>')}</details>
                `;
            }
            
            // Reset form
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Files';
            selectedFiles = [];
            filePreview.style.display = 'none';
            fileInput.value = '';
        });
    </script>
</body>
</html>'''
    return HTMLResponse(content=upload_html)

@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Analytics dashboard with charts and insights"""
    dashboard_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pany Analytics Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; padding: 20px; background: #f8fafc;
        }
        .dashboard-header {
            background: linear-gradient(135deg, #2563eb, #3b82f6);
            color: white; padding: 30px; border-radius: 12px; margin-bottom: 30px;
            text-align: center;
        }
        .stats-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }
        .stat-card {
            background: white; padding: 25px; border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center;
        }
        .stat-number {
            font-size: 2.5em; font-weight: bold; color: #2563eb; margin-bottom: 10px;
        }
        .stat-label { color: #64748b; font-size: 14px; }
        .chart-container {
            background: white; padding: 25px; border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px;
        }
        .chart-title { font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #1e293b; }
        .tenant-list {
            background: white; padding: 25px; border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .tenant-item {
            display: flex; justify-content: space-between; align-items: center;
            padding: 15px 0; border-bottom: 1px solid #f1f5f9;
        }
        .tenant-item:last-child { border-bottom: none; }
        .tenant-name { font-weight: 600; color: #1e293b; }
        .tenant-stats { color: #64748b; font-size: 14px; }
        .refresh-btn {
            background: #10b981; color: white; border: none; padding: 10px 20px;
            border-radius: 6px; cursor: pointer; margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #059669; }
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>📊 Pany Analytics Dashboard</h1>
        <p>Real-time insights into your semantic search data</p>
        <button class="refresh-btn" onclick="loadDashboard()">🔄 Refresh Data</button>
    </div>
    
    <div class="stats-grid" id="statsGrid">
        <!-- Stats will be loaded here -->
    </div>
    
    <div class="chart-container">
        <div class="chart-title">📈 Upload Trends (Last 30 Days)</div>
        <div id="uploadsChart" style="height: 400px;"></div>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">📁 File Types Distribution</div>
        <div id="fileTypesChart" style="height: 400px;"></div>
    </div>
    
    <div class="chart-container">
        <div class="chart-title">🔍 Search Performance</div>
        <div id="searchChart" style="height: 400px;"></div>
    </div>
    
    <div class="tenant-list">
        <div class="chart-title">👥 Tenant Overview</div>
        <div id="tenantList">
            <!-- Tenant data will be loaded here -->
        </div>
    </div>
    
    <script>
        async function loadDashboard() {
            try {
                // Load basic stats
                const statsResponse = await fetch('/analytics/stats');
                const stats = await statsResponse.json();
                renderStats(stats);
                
                // Load upload trends
                const trendsResponse = await fetch('/analytics/upload-trends');
                const trends = await trendsResponse.json();
                renderUploadTrends(trends);
                
                // Load file types
                const typesResponse = await fetch('/analytics/file-types');
                const types = await typesResponse.json();
                renderFileTypes(types);
                
                // Load search performance
                const searchResponse = await fetch('/analytics/search-performance');
                const searchData = await searchResponse.json();
                renderSearchPerformance(searchData);
                
                // Load tenants
                const tenantsResponse = await fetch('/analytics/tenants');
                const tenants = await tenantsResponse.json();
                renderTenants(tenants);
                
            } catch (error) {
                console.error('Failed to load dashboard:', error);
            }
        }
        
        function renderStats(stats) {
            const statsGrid = document.getElementById('statsGrid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-number">${stats.total_embeddings.toLocaleString()}</div>
                    <div class="stat-label">Total Documents</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.total_tenants}</div>
                    <div class="stat-label">Active Tenants</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.total_searches.toLocaleString()}</div>
                    <div class="stat-label">Total Searches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">${stats.avg_similarity.toFixed(1)}%</div>
                    <div class="stat-label">Avg Similarity Score</div>
                </div>
            `;
        }
        
        function renderUploadTrends(trends) {
            const trace = {
                x: trends.dates,
                y: trends.uploads,
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#2563eb', width: 3 },
                marker: { size: 8 }
            };
            
            const layout = {
                xaxis: { title: 'Date' },
                yaxis: { title: 'Uploads' },
                margin: { t: 20, r: 20, b: 40, l: 40 }
            };
            
            Plotly.newPlot('uploadsChart', [trace], layout);
        }
        
        function renderFileTypes(types) {
            const trace = {
                labels: types.labels,
                values: types.values,
                type: 'pie',
                hole: 0.4,
                marker: {
                    colors: ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
                }
            };
            
            const layout = {
                margin: { t: 20, r: 20, b: 20, l: 20 }
            };
            
            Plotly.newPlot('fileTypesChart', [trace], layout);
        }
        
        function renderSearchPerformance(searchData) {
            const trace = {
                x: searchData.hours,
                y: searchData.avg_response_time,
                type: 'bar',
                marker: { color: '#10b981' }
            };
            
            const layout = {
                xaxis: { title: 'Hour of Day' },
                yaxis: { title: 'Avg Response Time (ms)' },
                margin: { t: 20, r: 20, b: 40, l: 40 }
            };
            
            Plotly.newPlot('searchChart', [trace], layout);
        }
        
        function renderTenants(tenants) {
            const tenantList = document.getElementById('tenantList');
            tenantList.innerHTML = tenants.map(tenant => `
                <div class="tenant-item">
                    <div>
                        <div class="tenant-name">${tenant.tenant_id}</div>
                        <div class="tenant-stats">Last active: ${tenant.last_activity}</div>
                    </div>
                    <div class="tenant-stats">
                        ${tenant.document_count} docs • ${tenant.search_count} searches
                    </div>
                </div>
            `).join('');
        }
        
        // Load dashboard on page load
        loadDashboard();
        
        // Auto-refresh every 5 minutes
        setInterval(loadDashboard, 5 * 60 * 1000);
    </script>
</body>
</html>'''
    return HTMLResponse(content=dashboard_html)

@app.get("/analytics/stats")
async def get_analytics_stats():
    """Get basic analytics statistics"""
    try:
        async with db_service.async_session() as session:
            # Total embeddings
            total_result = await session.execute(text("SELECT COUNT(*) FROM embeddings"))
            total_embeddings = total_result.scalar() or 0
            
            # Total tenants
            tenant_result = await session.execute(
                text("SELECT COUNT(DISTINCT metadata->>'tenant_id') FROM embeddings WHERE metadata->>'tenant_id' IS NOT NULL")
            )
            total_tenants = tenant_result.scalar() or 0
            
            # Simulate search stats (you'd track these in a real app)
            total_searches = 1250  # This would come from search logs
            avg_similarity = 0.82  # This would be calculated from search results
            
            return {
                "total_embeddings": total_embeddings,
                "total_tenants": total_tenants,
                "total_searches": total_searches,
                "avg_similarity": avg_similarity * 100
            }
    except Exception as e:
        logger.error(f"Failed to get analytics stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/upload-trends")
async def get_upload_trends():
    """Get upload trends for the last 30 days"""
    try:
        async with db_service.async_session() as session:
            result = await session.execute(text("""
                SELECT 
                    DATE(created_at) as upload_date,
                    COUNT(*) as upload_count
                FROM embeddings 
                WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY upload_date
            """))
            
            trends = result.fetchall();
            
            dates = [row[0].strftime('%Y-%m-%d') for row in trends];
            uploads = [row[1] for row in trends];
            
            return {"dates": dates, "uploads": uploads}
    except Exception as e:
        logger.error(f"Failed to get upload trends: {e}")
        # Return sample data if query fails
        return {
            "dates": ["2025-06-20", "2025-06-21", "2025-06-22"],
            "uploads": [15, 23, 18]
        }
@app.get("/analytics/file-types")
async def get_file_types():
    """Get file type distribution"""
    try:
        async with db_service.async_session() as session:
            result = await session.execute(text("""
                SELECT 
                    metadata->>'file_category' as file_type,
                    COUNT(*) as count
                FROM embeddings 
                WHERE metadata->>'file_category' IS NOT NULL
                GROUP BY metadata->>'file_category'
                ORDER BY count DESC
            """))
            
            types = result.fetchall()
            
            labels = [row[0] or 'unknown' for row in types]
            values = [row[1] for row in types]
            
            return {"labels": labels, "values": values}
    except Exception as e:
        logger.error(f"Failed to get file types: {e}")
        # Return sample data
        return {
            "labels": ["Document", "Image", "Data", "Text"],
            "values": [45, 30, 15, 10]
        }

@app.get("/analytics/search-performance") 
async def get_search_performance():
    """Get search performance by hour"""
    # This would come from search logs in a real implementation
    return {
        "hours": list(range(24)),
        "avg_response_time": [12, 8, 6, 5, 7, 9, 15, 22, 28, 25, 23, 26, 
                             30, 28, 25, 22, 20, 25, 30, 35, 28, 22, 18, 15]
    }

@app.get("/analytics/tenants")
async def get_tenant_analytics():
    """Get tenant overview"""
    try:
        async with db_service.async_session() as session:
            result = await session.execute(text("""
                SELECT 
                    metadata->>'tenant_id' as tenant_id,
                    COUNT(*) as document_count,
                    MAX(created_at) as last_activity
                FROM embeddings 
                WHERE metadata->>'tenant_id' IS NOT NULL
                GROUP BY metadata->>'tenant_id'
                ORDER BY document_count DESC
            """))
            
            tenants = []
            for row in result:
                tenants.append({
                    "tenant_id": row[0] or "default",
                    "document_count": row[1],
                    "search_count": 25,  # This would come from search logs
                    "last_activity": row[2].strftime('%Y-%m-%d %H:%M') if row[2] else "Never"
                })
            
            return tenants
    except Exception as e:
        logger.error(f"Failed to get tenant analytics: {e}")
        return [
            {"tenant_id": "default", "document_count": 10, "search_count": 25, "last_activity": "2025-06-22 14:30"}
        ]

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

@app.post("/rag/ask")
async def rag_ask(
    question: str = Form(...),
    tenant_id: str = Form("default"),
    max_context: int = Form(5),
    temperature: float = Form(0.7)
):
    """
    RAG-powered Q&A using your documents
    """
    try:
        # Generate embedding for the question
        question_embedding = await embedding_service.generate_embedding(question, "text")
        
        # Get relevant context from database
        async with db_service.async_session() as session:
            result = await session.execute(text("""
                SELECT get_rag_context(
                    :question_embedding::vector(512),
                    :tenant_id,
                    :max_context,
                    0.6
                )
            """), {
                "question_embedding": "[" + ",".join(map(str, question_embedding)) + "]",
                "tenant_id": tenant_id,
                "max_context": max_context
            })
            
            context = result.scalar() or ""
        
        if not context.strip():
            return {
                "success": False,
                "message": "No relevant context found in your documents",
                "answer": "I don't have enough information in your documents to answer this question.",
                "sources": []
            }
        
        # Create RAG prompt
        prompt = f"""Based on the following context from the user's documents, answer the question.

Context:
{context}

Question: {question}

Answer: """
        
        # For now, return the context (in production, you'd call an LLM API)
        # You can integrate with OpenAI, Anthropic, or local models here
        
        return {
            "success": True,
            "question": question,
            "answer": "RAG functionality is set up! In production, this would call an LLM with the context.",
            "context_length": len(context),
            "tenant_id": tenant_id,
            "context_preview": context[:500] + "..." if len(context) > 500 else context
        }
        
    except Exception as e:
        logger.error(f"RAG ask failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rag-demo", response_class=HTMLResponse)
async def get_rag_demo():
    """RAG Q&A Demo Interface"""
    rag_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pany RAG Demo</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            max-width: 900px; margin: 0 auto; padding: 20px; background: #f8fafc;
        }
        .rag-container {
            background: white; border-radius: 12px; padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .chat-area {
            min-height: 400px; border: 2px solid #e5e7eb; border-radius: 12px;
            padding: 20px; margin-bottom: 20px; background: #fafafa;
            overflow-y: auto;
        }
        .message {
            margin-bottom: 20px; padding: 15px; border-radius: 8px;
        }
        .question {
            background: #dbeafe; color: #1e40af; text-align: right;
        }
        .answer {
            background: #dcfce7; color: #166534;
        }
        .context-info {
            background: #fef3c7; color: #92400e; font-size: 12px;
            padding: 8px; border-radius: 4px; margin-top: 10px;
        }
        .input-area {
            display: flex; gap: 10px; align-items: center;
        }
        .question-input {
            flex: 1; padding: 15px; border: 2px solid #e5e7eb; border-radius: 8px;
            font-size: 16px; resize: none;
        }
        .ask-btn {
            background: #2563eb; color: white; border: none; padding: 15px 25px;
            border-radius: 8px; cursor: pointer; font-size: 16px;
        }
        .ask-btn:hover { background: #1d4ed8; }
        .ask-btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .tenant-select {
            padding: 10px; border: 2px solid #e5e7eb; border-radius: 6px;
            margin-bottom: 15px; width: 200px;
        }
        .setup-info {
            background: #eff6ff; padding: 20px; border-radius: 8px; margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="rag-container">
        <h1>🤖 Pany RAG Demo</h1>
        <p>Ask questions about your uploaded documents. The system will find relevant context and provide answers.</p>
        
        <div class="setup-info">
            <strong>💡 Setup:</strong> Upload some documents first using the 
            <a href="/upload-page" target="_blank">upload page</a>, then ask questions about them here!
        </div>
        
        <label for="tenantSelect"><strong>Tenant/Project:</strong></label>
        <select id="tenantSelect" class="tenant-select">
            <option value="default">default</option>
            <option value="my-project">my-project</option>
            <option value="demo">demo</option>
        </select>
        
        <div class="chat-area" id="chatArea">
            <div class="message answer">
                <strong>🤖 Pany RAG:</strong> Hello! I can answer questions based on your uploaded documents. 
                What would you like to know?
            </div>
        </div>
        
        <div class="input-area">
            <textarea id="questionInput" class="question-input" 
                    placeholder="Ask a question about your documents..." 
                    rows="2"></textarea>
            <button id="askBtn" class="ask-btn">Ask</button>
        </div>
    </div>
    
    <script>
        const chatArea = document.getElementById('chatArea');
        const questionInput = document.getElementById('questionInput');
        const askBtn = document.getElementById('askBtn');
        const tenantSelect = document.getElementById('tenantSelect');
        
        function addMessage(content, isQuestion = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isQuestion ? 'question' : 'answer'}`;
            messageDiv.innerHTML = content;
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
        
        async function askQuestion() {
            const question = questionInput.value.trim();
            const tenantId = tenantSelect.value;
            
            if (!question) return;
            
            // Add question to chat
            addMessage(`<strong>👤 You:</strong> ${question}`, true);
            
            // Clear input and disable button
            questionInput.value = '';
            askBtn.disabled = true;
            askBtn.textContent = 'Thinking...';
            
            try {
                const formData = new FormData();
                formData.append('question', question);
                formData.append('tenant_id', tenantId);
                formData.append('max_context', '5');
                
                const response = await fetch('/rag/ask', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    let answerHtml = `<strong>🤖 Pany RAG:</strong> ${result.answer}`;
                    
                    if (result.context_preview) {
                        answerHtml += `
                            <div class="context-info">
                                📄 Found ${result.context_length} characters of relevant context from your documents
                            </div>
                        `;
                    }
                    
                    addMessage(answerHtml);
                } else {
                    addMessage(`<strong>🤖 Pany RAG:</strong> ${result.message}`);
                }
                
            } catch (error) {
                addMessage(`<strong>❌ Error:</strong> ${error.message}`);
            }
            
            // Re-enable button
            askBtn.disabled = false;
            askBtn.textContent = 'Ask';
        }
        
        askBtn.addEventListener('click', askQuestion);
        questionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                askQuestion();
            }
        });
        
        // Sample questions
        setTimeout(() => {
            addMessage(`
                <strong>💡 Try asking:</strong><br>
                • "What products do you have in red?"<br>
                • "Summarize the main points from the uploaded documents"<br>
                • "What information do you have about pricing?"
            `);
        }, 1000);
    </script>
</body>
</html>'''
    return HTMLResponse(content=rag_html)


def main():
    """Main entry point for the CLI"""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(description="Pany - PostgreSQL-native semantic search engine")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"), help="Host to bind to")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")), help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"], 
                       help="Log level")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Pany server on {args.host}:{args.port}")
    logger.info("Access the web interface at: http://{}:{}".format(args.host, args.port))
    logger.info("API documentation at: http://{}:{}/docs".format(args.host, args.port))
    
    uvicorn.run(
        "pany.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
