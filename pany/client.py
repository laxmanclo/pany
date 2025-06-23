"""
Pany Python Client
"""

import requests
import base64
import os
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import json


class PanyClient:
    """Python client for Pany semantic search"""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        """
        Initialize Pany client
        
        Args:
            host: Pany server host
            port: Pany server port
        """
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
    
    def upload_file(self, file_path: Union[str, Path], project_id: str) -> Dict[str, Any]:
        """
        Upload a file to Pany
        
        Args:
            file_path: Path to the file
            project_id: Project identifier
            
        Returns:
            Upload result
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            data = {'project_id': project_id}
            
            response = self.session.post(
                f"{self.base_url}/upload",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
    
    def search(self, query: str, project_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for content
        
        Args:
            query: Search query
            project_id: Project identifier
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        data = {
            "query": query,
            "project_id": project_id,
            "max_results": max_results
        }
        
        response = self.session.post(
            f"{self.base_url}/search",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def search_by_image(self, image_path: Union[str, Path], project_id: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search using an image
        
        Args:
            image_path: Path to image file
            project_id: Project identifier
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        image_path = Path(image_path)
        
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        with open(image_path, 'rb') as f:
            files = {'image': (image_path.name, f)}
            data = {
                'project_id': project_id,
                'max_results': max_results
            }
            
            response = self.session.post(
                f"{self.base_url}/search/image",
                files=files,
                data=data
            )
            response.raise_for_status()
            return response.json()
