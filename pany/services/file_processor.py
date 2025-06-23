import os
import io
import base64
from typing import List, Dict, Any, Optional
import pdfplumber
import pandas as pd
from PIL import Image
import logging

# Try to import magic, fall back to extension-based detection if not available
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic not available, using extension-based file type detection")

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
            
            # Try to detect MIME type using python-magic if available
            if MAGIC_AVAILABLE:
                try:
                    mime_type = magic.from_file(file_path, mime=True)
                    logger.debug(f"Detected MIME type: {mime_type}")
                except Exception as e:
                    logger.warning(f"Magic detection failed, using extension: {e}")
            
            # Categorize file based on extension
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
                "metadata": {
                    "file_category": "document",
                    "file_type": "pdf",
                    **metadata
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process PDF: {e}")
            raise
    
    async def process_image(self, file_path: str) -> Dict[str, Any]:
        """Process image file"""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Get image metadata
                metadata = {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode
                }
                
                # Convert to base64 for embedding
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return {
                "content": image_base64,
                "modality": "image",
                "metadata": {
                    "file_category": "image",
                    "file_type": file_path.split('.')[-1].lower(),
                    **metadata
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process image: {e}")
            raise
    
    async def process_csv(self, file_path: str) -> Dict[str, Any]:
        """Process CSV file"""
        try:
            df = pd.read_csv(file_path)
            
            # Convert to text representation
            text_content = f"CSV Data ({len(df)} rows, {len(df.columns)} columns):\n\n"
            text_content += f"Columns: {', '.join(df.columns)}\n\n"
            
            # Add first few rows as sample
            sample_size = min(10, len(df))
            text_content += f"Sample data (first {sample_size} rows):\n"
            text_content += df.head(sample_size).to_string(index=False)
            
            # Add summary statistics for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                text_content += "\n\nNumeric Summary:\n"
                text_content += df[numeric_cols].describe().to_string()
            
            metadata = {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "data_types": df.dtypes.to_dict()
            }
            
            return {
                "content": text_content,
                "modality": "text",
                "metadata": {
                    "file_category": "data",
                    "file_type": "csv",
                    **metadata
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process CSV: {e}")
            raise
    
    async def process_excel(self, file_path: str) -> Dict[str, Any]:
        """Process Excel file"""
        try:
            # Read all sheets
            excel_data = pd.read_excel(file_path, sheet_name=None)
            
            text_content = f"Excel File with {len(excel_data)} sheet(s):\n\n"
            
            total_rows = 0
            sheet_info = {}
            
            for sheet_name, df in excel_data.items():
                sheet_info[sheet_name] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": list(df.columns)
                }
                total_rows += len(df)
                
                text_content += f"Sheet: {sheet_name} ({len(df)} rows, {len(df.columns)} columns)\n"
                text_content += f"Columns: {', '.join(df.columns)}\n"
                
                # Add sample data
                sample_size = min(5, len(df))
                if sample_size > 0:
                    text_content += f"Sample data:\n{df.head(sample_size).to_string(index=False)}\n\n"
            
            metadata = {
                "sheets": len(excel_data),
                "total_rows": total_rows,
                "sheet_info": sheet_info
            }
            
            return {
                "content": text_content,
                "modality": "text",
                "metadata": {
                    "file_category": "data",
                    "file_type": "excel",
                    **metadata
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process Excel: {e}")
            raise
    
    async def process_text(self, file_path: str) -> Dict[str, Any]:
        """Process text file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            metadata = {
                "char_count": len(content),
                "line_count": len(content.split('\n')),
                "word_count": len(content.split())
            }
            
            return {
                "content": content,
                "modality": "text",
                "metadata": {
                    "file_category": "document",
                    "file_type": file_path.split('.')[-1].lower(),
                    **metadata
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process text file: {e}")
            raise
    
    async def process_file(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Process file based on type"""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_file_size:
                raise ValueError(f"File too large: {file_size} bytes (max: {self.max_file_size})")
            
            # Detect file type
            category, ext = self.detect_file_type(file_path)
            
            logger.info(f"Processing {category} file: {original_filename} ({ext})")
            
            # Process based on category
            if category == 'document':
                if ext == 'pdf':
                    return await self.process_pdf(file_path)
                else:
                    return await self.process_text(file_path)
            elif category == 'image':
                return await self.process_image(file_path)
            elif category == 'data':
                if ext == 'csv':
                    return await self.process_csv(file_path)
                elif ext in ['xlsx', 'xls']:
                    return await self.process_excel(file_path)
                else:
                    # Fallback to text processing
                    return await self.process_text(file_path)
            else:
                # Unknown type, try text processing
                logger.warning(f"Unknown file type {ext}, attempting text processing")
                return await self.process_text(file_path)
                
        except Exception as e:
            logger.error(f"Failed to process file {original_filename}: {e}")
            raise

# Global file processor instance
file_processor = FileProcessor()
