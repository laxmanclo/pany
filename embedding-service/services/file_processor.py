import os
import io
import base64
from typing import List, Dict, Any, Optional
import pdfplumber
import pandas as pd
import magic
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class FileProcessor:
    """Advanced file processing for multiple formats"""
    
    SUPPORTED_TYPES = {
        'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'],
        'document': ['pdf', 'txt', 'md'],
        'data': ['csv', 'xlsx', 'xls', 'json']
    }
    
    def __init__(self):
        self.max_file_size = 50 * 1024 * 1024  # 50MB
    
    def detect_file_type(self, file_path: str) -> tuple[str, str]:
        """Detect file type and category"""
        try:
            # Get file extension
            ext = file_path.split('.')[-1].lower()
            
            # Detect MIME type using python-magic
            mime_type = magic.from_file(file_path, mime=True)
            
            # Categorize file
            category = 'unknown'
            for cat, extensions in self.SUPPORTED_TYPES.items():
                if ext in extensions:
                    category = cat
                    break
            
            return category, ext
            
        except Exception as e:
            logger.error(f"Failed to detect file type: {e}")
            return 'unknown', 'unknown'
    
    async def process_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text from PDF"""
        try:
            text_content = ""
            metadata = {"pages": 0, "text_length": 0}
            
            with pdfplumber.open(file_path) as pdf:
                metadata["pages"] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_content += f"\n--- Page {page_num + 1} ---\n"
                        text_content += page_text
            
            metadata["text_length"] = len(text_content)
            
            return {
                "content": text_content.strip(),
                "modality": "text",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            raise ValueError(f"PDF processing failed: {e}")
    
    async def process_csv(self, file_path: str) -> Dict[str, Any]:
        """Process CSV/Excel files"""
        try:
            # Read the file
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # Convert to text representation
            content_parts = []
            
            # Add column headers
            content_parts.append("Columns: " + ", ".join(df.columns.tolist()))
            
            # Add sample rows (first 5)
            content_parts.append("\nSample data:")
            for idx, row in df.head().iterrows():
                row_text = " | ".join([f"{col}: {val}" for col, val in row.items()])
                content_parts.append(f"Row {idx + 1}: {row_text}")
            
            # Add summary statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                content_parts.append(f"\nNumeric columns summary:")
                for col in numeric_cols:
                    stats = df[col].describe()
                    content_parts.append(f"{col}: mean={stats['mean']:.2f}, min={stats['min']}, max={stats['max']}")
            
            content = "\n".join(content_parts)
            
            metadata = {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist(),
                "numeric_columns": numeric_cols.tolist(),
                "file_type": "csv" if file_path.endswith('.csv') else "excel"
            }
            
            return {
                "content": content,
                "modality": "text",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process CSV/Excel: {e}")
            raise ValueError(f"CSV/Excel processing failed: {e}")
    
    async def process_image(self, file_path: str) -> Dict[str, Any]:
        """Process image files"""
        try:
            # Read and convert image to base64
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            
            # Validate image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to base64
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            metadata = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
                "size_bytes": len(image_bytes)
            }
            
            return {
                "content": image_b64,
                "modality": "image",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            raise ValueError(f"Image processing failed: {e}")
    
    async def process_text(self, file_path: str) -> Dict[str, Any]:
        """Process text files"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            metadata = {
                "char_count": len(content),
                "word_count": len(content.split()),
                "line_count": len(content.split('\n'))
            }
            
            return {
                "content": content,
                "modality": "text",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process text file: {e}")
            raise ValueError(f"Text processing failed: {e}")
    
    async def process_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """Main file processing function"""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                raise ValueError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
            
            # Detect file type
            category, extension = self.detect_file_type(file_path)
            
            # Process based on category
            if category == 'document':
                if extension == 'pdf':
                    result = await self.process_pdf(file_path)
                else:
                    result = await self.process_text(file_path)
            elif category == 'data':
                result = await self.process_csv(file_path)
            elif category == 'image':
                result = await self.process_image(file_path)
            else:
                # Try as text file
                result = await self.process_text(file_path)
            
            # Add common metadata
            result["metadata"].update({
                "filename": filename,
                "file_size": file_size,
                "file_category": category,
                "file_extension": extension
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process file {filename}: {e}")
            raise

# Global file processor instance
file_processor = FileProcessor()
