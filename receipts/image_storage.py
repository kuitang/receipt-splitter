"""
In-memory image storage for receipt images.
Images are stored in Django's cache for temporary access during editing.
"""

import io
import logging
from django.core.cache import cache
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

logger = logging.getLogger(__name__)

# Cache timeout for images (2 hours)
IMAGE_CACHE_TIMEOUT = 2 * 60 * 60


def store_receipt_image_in_memory(receipt_id, image_file):
    """
    Store a receipt image in memory (Django cache).
    
    Args:
        receipt_id: UUID of the receipt
        image_file: The uploaded image file
        
    Returns:
        bool: True if stored successfully
    """
    try:
        # Read the image file into memory
        image_file.seek(0)
        image_bytes = image_file.read()
        image_file.seek(0)
        
        # Store in cache with receipt ID as key
        cache_key = f"receipt_image_{receipt_id}"
        cache.set(cache_key, image_bytes, timeout=IMAGE_CACHE_TIMEOUT)
        
        # Also store the content type
        content_type = getattr(image_file, 'content_type', 'image/jpeg')
        cache.set(f"{cache_key}_type", content_type, timeout=IMAGE_CACHE_TIMEOUT)
        
        logger.info(f"Stored image for receipt {receipt_id} in memory")
        return True
        
    except Exception as e:
        logger.error(f"Failed to store image in memory: {str(e)}")
        return False


def get_receipt_image_from_memory(receipt_id):
    """
    Retrieve a receipt image from memory.
    
    Args:
        receipt_id: UUID of the receipt
        
    Returns:
        tuple: (image_bytes, content_type) or (None, None) if not found
    """
    cache_key = f"receipt_image_{receipt_id}"
    image_bytes = cache.get(cache_key)
    
    if image_bytes:
        content_type = cache.get(f"{cache_key}_type", "image/jpeg")
        return image_bytes, content_type
    
    return None, None


def delete_receipt_image_from_memory(receipt_id):
    """
    Delete a receipt image from memory.
    
    Args:
        receipt_id: UUID of the receipt
    """
    cache_key = f"receipt_image_{receipt_id}"
    cache.delete(cache_key)
    cache.delete(f"{cache_key}_type")
    logger.info(f"Deleted image for receipt {receipt_id} from memory")