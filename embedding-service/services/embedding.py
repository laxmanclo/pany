import asyncio
import logging
import time
import base64
import io
import os
from typing import List, Optional, Tuple
from PIL import Image
import torch
import open_clip
import numpy as np
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings using CLIP model"""
    
    def __init__(self):
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._is_ready = False
        logger.info(f"Using device: {self.device}")
    
    async def initialize(self):
        """Initialize the CLIP model"""
        try:
            logger.info("Loading CLIP model: ViT-B-32")
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                'ViT-B-32', 
                pretrained='openai',
                device=self.device
            )
            self.tokenizer = open_clip.get_tokenizer('ViT-B-32')
            self._is_ready = True
            logger.info("CLIP model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self._is_ready and self.model is not None
    
    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decode base64 string to PIL Image"""
        try:
            # Remove data URL prefix if present
            if "," in base64_string:
                base64_string = base64_string.split(",")[1]
            
            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
        except Exception as e:
            raise ValueError(f"Invalid base64 image data: {e}")
    
    def _validate_image_size(self, image_bytes: bytes):
        """Validate image size"""
        max_size = getattr(settings, 'max_image_size', 10 * 1024 * 1024)  # 10MB default
        if len(image_bytes) > max_size:
            raise ValueError(f"Image size {len(image_bytes)} exceeds maximum {max_size}")
    
    async def generate_text_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using CLIP"""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        try:
            # Tokenize text
            text_tokens = self.tokenizer([text]).to(self.device)
            
            # Generate embedding
            with torch.no_grad():
                text_features = self.model.encode_text(text_tokens)
                # Normalize the features
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
            # Convert to list
            embedding = text_features.cpu().numpy().flatten().tolist()
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate text embedding: {e}")
            raise
    
    async def generate_image_embedding(self, image_data: str) -> List[float]:
        """Generate embedding for image using CLIP"""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        try:
            # Decode base64 image
            image = self._decode_base64_image(image_data)
            
            # Preprocess image
            image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
            
            # Generate embedding
            with torch.no_grad():
                image_features = self.model.encode_image(image_tensor)
                # Normalize the features
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
            # Convert to list
            embedding = image_features.cpu().numpy().flatten().tolist()
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate image embedding: {e}")
            raise
    
    async def generate_embedding(self, content: str, modality: str) -> List[float]:
        """Generate embedding based on modality"""
        if modality == "text":
            return await self.generate_text_embedding(content)
        elif modality == "image":
            return await self.generate_image_embedding(content)
        else:
            raise ValueError(f"Unsupported modality: {modality}")
    
    async def process_uploaded_file(self, file_path: str, content_id: str, project_id: str) -> dict:
        """Process an uploaded file and generate embeddings"""
        start_time = time.time()
        
        try:
            # Determine file type
            file_extension = file_path.split('.')[-1].lower()
            
            if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                # Process as image
                with open(file_path, 'rb') as f:
                    image_bytes = f.read()
                
                # Convert to base64
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                
                # Generate embedding
                embedding = await self.generate_image_embedding(image_b64)
                modality = "image"
                content = f"Image file: {os.path.basename(file_path)}"
                
            else:
                # Process as text file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Generate embedding
                embedding = await self.generate_text_embedding(content)
                modality = "text"
            
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            return {
                "content_id": content_id,
                "modality": modality,
                "content": content,
                "embedding": embedding,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            raise

# Global service instance
embedding_service = EmbeddingService()
