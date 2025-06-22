import asyncio
import aiohttp
import base64
import json
import time
from typing import Dict, Any

# Configuration
API_BASE_URL = "http://localhost:8000"

class PanyClient:
    """Client for testing the Pany Embedding Service"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()
    
    async def create_text_embedding(self, content_id: str, text: str, metadata: Dict = None) -> Dict[str, Any]:
        """Create embedding for text"""
        data = {
            "content_id": content_id,
            "modality": "text",
            "content": text,
            "metadata": metadata or {}
        }
        
        async with self.session.post(f"{self.base_url}/embeddings", json=data) as response:
            return await response.json()
    
    async def create_image_embedding(self, content_id: str, image_path: str, metadata: Dict = None) -> Dict[str, Any]:
        """Create embedding for image"""
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        data = {
            "content_id": content_id,
            "modality": "image",
            "content": f"data:image/jpeg;base64,{image_data}",
            "metadata": metadata or {"filename": image_path}
        }
        
        async with self.session.post(f"{self.base_url}/embeddings", json=data) as response:
            return await response.json()
    
    async def search_text(self, query: str, target_modality: str = None, max_results: int = 5) -> Dict[str, Any]:
        """Search using text query"""
        data = {
            "query": query,
            "query_modality": "text",
            "target_modality": target_modality,
            "similarity_threshold": 0.5,
            "max_results": max_results
        }
        
        async with self.session.post(f"{self.base_url}/search", json=data) as response:
            return await response.json()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get API statistics"""
        async with self.session.get(f"{self.base_url}/stats") as response:
            return await response.json()

async def test_basic_functionality():
    """Test basic API functionality"""
    print("🚀 Testing Pany Embedding Service...")
    
    async with PanyClient() as client:
        # Health check
        print("\n1. Health Check:")
        health = await client.health_check()
        print(f"   Status: {health['status']}")
        print(f"   Database: {'✅' if health['database_connected'] else '❌'}")
        print(f"   Model: {'✅' if health['model_loaded'] else '❌'}")
        
        if health['status'] != 'healthy':
            print("❌ Service not healthy, stopping tests")
            return
        
        # Test text embeddings
        print("\n2. Creating Text Embeddings:")
        test_texts = [
            ("doc1", "A beautiful sunset over the mountains with golden light", {"category": "nature"}),
            ("doc2", "Modern city skyline with tall buildings and busy streets", {"category": "urban"}),
            ("doc3", "Cute cat playing with a ball of yarn in the garden", {"category": "animals"}),
            ("doc4", "Fresh pizza with melted cheese and pepperoni toppings", {"category": "food"}),
        ]
        
        for content_id, text, metadata in test_texts:
            try:
                result = await client.create_text_embedding(content_id, text, metadata)
                print(f"   ✅ {content_id}: {text[:50]}...")
            except Exception as e:
                print(f"   ❌ {content_id}: Error - {e}")
        
        # Test search
        print("\n3. Testing Similarity Search:")
        search_queries = [
            "Beautiful landscape with mountains",
            "Urban architecture and buildings", 
            "Adorable pet animals",
            "Delicious Italian food"
        ]
        
        for query in search_queries:
            try:
                results = await client.search_text(query, max_results=3)
                print(f"\n   Query: '{query}'")
                print(f"   Found {results['total_results']} results in {results['execution_time_ms']:.2f}ms:")
                
                for i, result in enumerate(results['results'], 1):
                    print(f"     {i}. {result['content_id']} (similarity: {result['similarity']:.3f})")
                    print(f"        Content: {result['content'][:60]}...")
                    
            except Exception as e:
                print(f"   ❌ Query failed: {e}")
        
        # Get stats
        print("\n4. Database Statistics:")
        try:
            stats = await client.get_stats()
            print(f"   Total embeddings: {stats['total_embeddings']}")
            print(f"   Embedding dimension: {stats['embedding_dimension']}")
            print(f"   Model: {stats['model']}")
        except Exception as e:
            print(f"   ❌ Failed to get stats: {e}")

async def test_cross_modal_search():
    """Test cross-modal search capabilities"""
    print("\n🔄 Testing Cross-Modal Search...")
    
    async with PanyClient() as client:
        # This would require actual images - for now just demonstrate the concept
        print("   Note: Cross-modal search requires actual images")
        print("   See examples/sample_images/ for image testing")
        
        # Test text-to-text search with different similarity thresholds
        print("\n   Testing different similarity thresholds:")
        query = "Mountain landscape"
        
        for threshold in [0.3, 0.5, 0.7, 0.9]:
            try:
                data = {
                    "query": query,
                    "query_modality": "text",
                    "similarity_threshold": threshold,
                    "max_results": 5
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{API_BASE_URL}/search", json=data) as response:
                        results = await response.json()
                        print(f"   Threshold {threshold}: {results['total_results']} results")
                        
            except Exception as e:
                print(f"   ❌ Threshold {threshold}: {e}")

async def performance_benchmark():
    """Run performance benchmarks"""
    print("\n⚡ Performance Benchmark...")
    
    async with PanyClient() as client:
        # Batch embedding creation
        print("\n   Creating embeddings in batch:")
        start_time = time.time()
        
        tasks = []
        for i in range(10):
            content_id = f"perf_test_{i}"
            text = f"Performance test document number {i} with some random content about various topics"
            task = client.create_text_embedding(content_id, text, {"test": "performance"})
            tasks.append(task)
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            successful = sum(1 for r in results if not isinstance(r, Exception))
            total_time = (end_time - start_time) * 1000
            
            print(f"   Created {successful}/10 embeddings in {total_time:.2f}ms")
            print(f"   Average: {total_time/successful:.2f}ms per embedding")
            
        except Exception as e:
            print(f"   ❌ Batch creation failed: {e}")
        
        # Batch search
        print("\n   Running search benchmark:")
        search_queries = [
            "performance test", "random content", "various topics", 
            "document analysis", "text processing"
        ]
        
        start_time = time.time()
        search_tasks = [client.search_text(q, max_results=3) for q in search_queries]
        
        try:
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            end_time = time.time()
            
            successful_searches = sum(1 for r in search_results if not isinstance(r, Exception))
            total_search_time = (end_time - start_time) * 1000
            
            print(f"   Completed {successful_searches}/5 searches in {total_search_time:.2f}ms")
            print(f"   Average: {total_search_time/successful_searches:.2f}ms per search")
            
        except Exception as e:
            print(f"   ❌ Batch search failed: {e}")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 PANY EMBEDDING SERVICE TEST SUITE")
    print("=" * 60)
    
    try:
        await test_basic_functionality()
        await test_cross_modal_search() 
        await performance_benchmark()
        
        print("\n" + "=" * 60)
        print("✅ Test suite completed!")
        print("💡 Next steps:")
        print("   - Add real images to test cross-modal search")
        print("   - Try the web interface at http://localhost:8000/docs")
        print("   - Check database with: docker exec -it pany_postgres psql -U pany_user -d pany_vectordb")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
