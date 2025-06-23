import asyncio
import logging
import time
import base64
import io
import os
from typing import List, Optional, Tuple
from PIL import Image
import torch
import numpy as np
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating embeddings using SentenceTransformers"""
    
    def __init__(self):
        self.text_model = None
        self.image_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._is_ready = False
        logger.info(f"Using device: {self.device}")
    
    async def initialize(self):
        """Initialize the embedding models"""
        try:
            logger.info("Loading SentenceTransformer models...")
            
            # Load text embedding model
            self.text_model = SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
            
            # For multimodal support, use CLIP-like model if available
            try:
                self.image_model = SentenceTransformer('clip-ViT-B-32', device=self.device)
                logger.info("Loaded both text and image models")
            except Exception as e:
                logger.warning(f"Could not load image model, text-only mode: {e}")
                self.image_model = None
            
            self._is_ready = True
            logger.info("Embedding models loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding models: {e}")
            raise
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self._is_ready and self.text_model is not None
    
    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decode base64 string to PIL Image"""
        try:
            # Remove data URL prefix if present
            if "," in base64_string:
                base64_string = base64_string.split(",")[1]
            
            image_bytes = base64.b64decode(base64_string)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':                image = image.convert('RGB')
            
            return image
        except Exception as e:
            raise ValueError(f"Invalid base64 image data: {e}")
    
    def _validate_image_size(self, image_bytes: bytes):
        """Validate image size"""
        max_size = 10 * 1024 * 1024  # 10MB default
        if len(image_bytes) > max_size:
            raise ValueError(f"Image size {len(image_bytes)} exceeds maximum {max_size}")
    
    async def generate_text_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using SentenceTransformers"""
        if not self.text_model:
            raise RuntimeError("Text model not initialized")
        
        try:
            # Generate embedding
            embedding = self.text_model.encode(text, convert_to_tensor=False)
            
            # Ensure it's a list of floats
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate text embedding: {e}")
            raise
    
    async def generate_image_embedding(self, image_data: str) -> List[float]:
        """Generate embedding for image using SentenceTransformers"""
        if not self.image_model:
            # Fall back to text model for image descriptions if no image model
            logger.warning("No image model available, using text fallback")
            return await self.generate_text_embedding(f"Image content: {image_data[:100]}")
        
        try:
            # Decode base64 image
            image = self._decode_base64_image(image_data)
            
            # Generate embedding using sentence-transformers image model
            embedding = self.image_model.encode(image, convert_to_tensor=False)
            
            # Ensure it's a list of floats
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate image embedding: {e}")
            # Fall back to text description
            return await self.generate_text_embedding(f"Image processing failed: {str(e)[:100]}")
    
    async def generate_embedding(self, content: str, modality: str) -> List[float]:
        """Generate embedding based on modality"""
        if modality == "text":
            return await self.generate_text_embedding(content)
        elif modality == "image":
            return await self.generate_image_embedding(content)
        else:
            raise ValueError(f"Unsupported modality: {modality}")
    
    async def process_uploaded_file(self, file_path: str, file_id: str, folder: str) -> dict:
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
                import base64
                image_b64 = base64.b64encode(image_bytes).decode('utf-8')
                
                # Generate embedding
                embedding = await self.generate_image_embedding(image_b64)
                modality = "image"
                content = f"Image file: {os.path.basename(file_path)}"
                
            else:
                # Process as text
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Try with different encoding
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                
                # Truncate if too long
                if len(content) > 8000:
                    content = content[:8000] + "..."
                
                embedding = await self.generate_text_embedding(content)
                modality = "text"
            
            end_time = time.time()
            processing_time = (end_time - start_time) * 1000
            
            return {
                "content_id": file_id,
                "modality": modality,
                "content": content,
                "embedding": embedding,
                "processing_time_ms": processing_time
            }
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            raise

# Create global instance
embedding_service = EmbeddingService()
