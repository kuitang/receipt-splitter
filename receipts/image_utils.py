"""
Image utilities for handling various image formats
"""

import io
import logging
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

# Required HEIC support
import pillow_heif
pillow_heif.register_heif_opener()
HEIC_SUPPORT = True


def convert_to_jpeg_if_needed(uploaded_file):
    """
    Convert uploaded image to WebP if it's in HEIC format.
    Chrome and many browsers cannot display HEIC files directly.
    Returns an in-memory file, no disk operations.

    When client-side optimization works, images arrive as WebP or JPEG
    and pass through unchanged. This only activates for raw HEIC uploads
    (e.g. desktop Chrome where HEIC can't be decoded client-side).

    Args:
        uploaded_file: Django UploadedFile object

    Returns:
        Django UploadedFile object (original or converted to WebP in memory)
    """

    if not uploaded_file:
        return uploaded_file

    # Check if the file is HEIC/HEIF
    filename = uploaded_file.name.lower()
    is_heic = filename.endswith('.heic') or filename.endswith('.heif')

    if not is_heic:
        # Not HEIC, return as-is
        return uploaded_file

    try:
        # Read the HEIC image into memory
        uploaded_file.seek(0)
        image_bytes = uploaded_file.read()
        image_bytes_len = len(image_bytes)

        # Open with PIL (pillow-heif handles HEIC) - in memory
        image = Image.open(io.BytesIO(image_bytes))

        # WebP supports RGBA, but convert palette/other modes
        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')

        # Save as WebP to memory buffer
        output = io.BytesIO()
        image.save(output, format='WEBP', quality=85)
        output.seek(0)

        # Create new uploaded file with WebP content (in memory)
        new_filename = filename.rsplit('.', 1)[0] + '.webp'
        converted_file = InMemoryUploadedFile(
            output,
            'ImageField',
            new_filename,
            'image/webp',
            output.getbuffer().nbytes,
            None
        )

        logger.info(
            f"Image conversion: {filename} ({image_bytes_len:,} bytes) "
            f"-> {new_filename} ({output.getbuffer().nbytes:,} bytes)"
        )
        return converted_file

    except Exception as e:
        logger.exception("Failed to convert HEIC file")
        raise ValueError("Failed to process HEIC file.")


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
    
    logger.info(f"OCR input: format={format_hint}, size={len(image_bytes):,} bytes")
    return image_bytes, format_hint