"""
Image utilities for handling various image formats
"""

import io
import logging
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

# Try to import pillow-heif for HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False
    logger.warning("pillow-heif not installed. HEIC files will not be supported.")


def convert_to_jpeg_if_needed(uploaded_file):
    """
    Convert uploaded image to JPEG if it's in HEIC format.
    Chrome and many browsers cannot display HEIC files directly.
    Returns an in-memory file, no disk operations.
    
    Args:
        uploaded_file: Django UploadedFile object
        
    Returns:
        Django UploadedFile object (original or converted to JPEG in memory)
    """
    
    if not uploaded_file:
        return uploaded_file
    
    # Check if the file is HEIC/HEIF
    filename = uploaded_file.name.lower()
    is_heic = filename.endswith('.heic') or filename.endswith('.heif')
    
    if not is_heic:
        # Not HEIC, return as-is
        return uploaded_file
    
    if not HEIC_SUPPORT:
        logger.error("Cannot convert HEIC file - pillow-heif not installed")
        raise ValueError("HEIC format is not supported. Please upload a JPEG or PNG file.")
    
    try:
        # Read the HEIC image into memory
        uploaded_file.seek(0)
        image_bytes = uploaded_file.read()
        
        # Open with PIL (pillow-heif handles HEIC) - in memory
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (HEIC might have alpha channel)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save as JPEG to memory buffer
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=95)
        output.seek(0)
        
        # Create new uploaded file with JPEG content (in memory)
        new_filename = filename.rsplit('.', 1)[0] + '.jpg'
        converted_file = InMemoryUploadedFile(
            output,
            'ImageField',
            new_filename,
            'image/jpeg',
            output.getbuffer().nbytes,
            None
        )
        
        logger.info(f"Converted HEIC file {filename} to JPEG {new_filename} in memory")
        return converted_file
        
    except Exception as e:
        logger.error(f"Failed to convert HEIC file: {str(e)}")
        raise ValueError(f"Failed to process HEIC file: {str(e)}")


def get_image_bytes_for_ocr(uploaded_file):
    """
    Get image bytes suitable for OCR processing.
    Handles HEIC files by reading the original uploaded content.
    
    Args:
        uploaded_file: Django UploadedFile object
        
    Returns:
        tuple: (image_bytes, format_hint)
    """
    
    uploaded_file.seek(0)
    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    
    # Detect format from filename
    filename = uploaded_file.name.lower()
    format_hint = "JPEG"  # Default
    
    if filename.endswith('.heic') or filename.endswith('.heif'):
        format_hint = "HEIC"
    elif filename.endswith('.png'):
        format_hint = "PNG"
    elif filename.endswith('.webp'):
        format_hint = "WEBP"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        format_hint = "JPEG"
    
    return image_bytes, format_hint