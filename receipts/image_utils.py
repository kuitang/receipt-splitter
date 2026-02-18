"""
Image utilities for handling various image formats.

All format detection uses libmagic — file extensions are never trusted.
"""

import io
import logging
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
import magic

logger = logging.getLogger(__name__)

# Required HEIC support
import pillow_heif
pillow_heif.register_heif_opener()

HEIC_MIME_TYPES = {'image/heic', 'image/heif'}

MIME_TO_FORMAT_HINT = {
    'image/heic': 'HEIC',
    'image/heif': 'HEIC',
    'image/jpeg': 'JPEG',
    'image/png': 'PNG',
    'image/webp': 'WEBP',
}


def detect_mime(uploaded_file):
    """Detect MIME type of an uploaded file using libmagic."""
    uploaded_file.seek(0)
    header = uploaded_file.read(8192)
    uploaded_file.seek(0)
    return magic.from_buffer(header, mime=True)


def convert_to_jpeg_if_needed(uploaded_file):
    """
    Convert uploaded image to WebP if it's actually HEIC/HEIF content.

    Uses libmagic for detection — file extensions are ignored.
    When client-side optimization works, images arrive as WebP or JPEG
    and pass through unchanged. This only activates for actual HEIC content.

    Args:
        uploaded_file: Django UploadedFile object

    Returns:
        Django UploadedFile object (original or converted to WebP in memory)
    """
    if not uploaded_file:
        return uploaded_file

    detected_mime = detect_mime(uploaded_file)
    logger.info(
        f"Image format detection: name={uploaded_file.name}, "
        f"detected_mime={detected_mime}"
    )

    if detected_mime not in HEIC_MIME_TYPES:
        return uploaded_file

    try:
        uploaded_file.seek(0)
        image_bytes = uploaded_file.read()
        image_bytes_len = len(image_bytes)

        image = Image.open(io.BytesIO(image_bytes))

        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGB')

        output = io.BytesIO()
        image.save(output, format='WEBP', quality=85)
        output.seek(0)

        # Derive output filename from the original name, replacing extension
        original_name = uploaded_file.name
        base = original_name.rsplit('.', 1)[0] if '.' in original_name else original_name
        new_filename = base + '.webp'

        converted_file = InMemoryUploadedFile(
            output,
            'ImageField',
            new_filename,
            'image/webp',
            output.getbuffer().nbytes,
            None
        )

        logger.info(
            f"Image conversion: {original_name} ({image_bytes_len:,} bytes) "
            f"-> {new_filename} ({output.getbuffer().nbytes:,} bytes)"
        )
        return converted_file

    except Exception:
        logger.exception("Failed to convert HEIC file")
        raise ValueError("Failed to process HEIC file.")


def get_image_bytes_for_ocr(uploaded_file):
    """
    Get image bytes suitable for OCR processing.

    Uses libmagic for format detection — file extensions are ignored.

    Args:
        uploaded_file: Django UploadedFile object

    Returns:
        tuple: (image_bytes, format_hint)
    """
    detected_mime = detect_mime(uploaded_file)

    uploaded_file.seek(0)
    image_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    format_hint = MIME_TO_FORMAT_HINT.get(detected_mime, 'JPEG')

    logger.info(
        f"OCR input: detected_mime={detected_mime}, "
        f"format={format_hint}, size={len(image_bytes):,} bytes"
    )
    return image_bytes, format_hint
