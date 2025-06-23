"""
Pany - PostgreSQL-native semantic search engine with multi-modal support

A self-hosted semantic search solution that leverages PostgreSQL's vector capabilities
for efficient similarity search across text, images, and documents.
"""

__version__ = '0.1.0'
__author__ = 'Laxman Srivastava'
__email__ = 'laxmansrivastacc@gmail.com'

from .main import app
from .config import settings
from .client import PanyClient

__all__ = ['app', 'settings', 'PanyClient']
