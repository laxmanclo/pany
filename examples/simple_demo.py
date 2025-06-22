#!/usr/bin/env python3
"""
Super Simple Pany API Test - Shows how dead simple the API is
This is exactly what you wanted: requests.post('api.pany.cloud/upload', files={'image': open('photo.jpg')})
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8000"
USER_ID = "demo-user"
PROJECT_ID = "demo-project"

def upload_file(file_path: str):
    """Dead simple file upload"""
    print(f"📤 Uploading {file_path}...")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'user_id': USER_ID,
            'project_id': PROJECT_ID
        }
        
        response = requests.post(f'{API_BASE}/upload', files=files, data=data)
        
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success: {result['message']}")
        print(f"   Content ID: {result['content_id']}")
        print(f"   Processing time: {result['processing_time_ms']:.2f}ms")
        return result['content_id']
    else:
        print(f"❌ Upload failed: {response.text}")
        return None

def search_content(query: str):
    """Dead simple search"""
    print(f"🔍 Searching for: '{query}'...")
    
    data = {
        'query': query,
        'project_id': PROJECT_ID,
        'max_results': 5
    }
    
    response = requests.post(f'{API_BASE}/simple-search', data=data)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Found {result['total_results']} results:")
        
        for i, item in enumerate(result['results'], 1):
            print(f"   {i}. {item['content'][:60]}...")
            print(f"      Similarity: {item['similarity']*100:.1f}% | Type: {item['modality']}")
            print()
    else:
        print(f"❌ Search failed: {response.text}")

def create_test_files():
    """Create some test files to upload"""
    test_files = {
        'test_doc.txt': 'This is a beautiful sunset over the mountains with golden light reflecting on the calm lake water.',
        'product_description.txt': 'Premium red leather shoes with comfortable cushioning and elegant design perfect for formal occasions.',
        'nature_article.txt': 'The forest ecosystem is home to diverse wildlife including bears, deer, and countless bird species.',
        'tech_content.txt': 'Machine learning algorithms can process vast amounts of data to identify patterns and make predictions.'
    }
    
    for filename, content in test_files.items():
        with open(filename, 'w') as f:
            f.write(content)
        print(f"📝 Created test file: {filename}")

def main():
    """Demonstrate the dead simple API"""
    print("🚀 Pany API Demo - Dead Simple File Search")
    print("=" * 50)
    
    # Check if API is running
    try:
        response = requests.get(f'{API_BASE}/health')
        if response.status_code != 200:
            print("❌ API is not running. Start with: python -m uvicorn main:app --reload")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Can't connect to API. Make sure it's running on localhost:8000")
        return
    
    print("✅ API is running!\n")
    
    # Create test files
    print("📁 Creating test files...")
    create_test_files()
    print()
    
    # Upload files (the magic happens here - user doesn't need to know about embeddings)
    print("📤 Uploading files...")
    test_files = ['test_doc.txt', 'product_description.txt', 'nature_article.txt', 'tech_content.txt']
    
    for file_path in test_files:
        upload_file(file_path)
        time.sleep(1)  # Be nice to the API
    
    print("\n" + "="*50)
    
    # Search (also dead simple)
    print("🔍 Testing search...")
    search_queries = [
        "red shoes",
        "mountain sunset", 
        "forest animals",
        "machine learning data"
    ]
    
    for query in search_queries:
        search_content(query)
        time.sleep(1)
    
    print("🎉 Demo complete!")
    print("\nNow open dashboard.html to see the web interface!")
    print("Or embed the widget in your site with:")
    print('<script src="http://localhost:8000/widget.js" data-project="demo-project"></script>')

if __name__ == "__main__":
    main()
