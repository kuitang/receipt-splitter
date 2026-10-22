"""Local upload regressions for the Pillow security upgrade."""
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from receipts.validators import FileUploadValidator


@pytest.mark.backend
@pytest.mark.parametrize('fmt,mime', [('PNG', 'image/png'), ('JPEG', 'image/jpeg'), ('WEBP', 'image/webp')])
def test_valid_formats_with_exif_are_readable_and_private(fmt, mime):
    image = Image.new('RGB', (4, 6), 'red')
    exif = Image.Exif()
    exif[0x010E] = 'private receipt metadata'
    raw = BytesIO()
    image.save(raw, format=fmt, exif=exif)
    upload = SimpleUploadedFile('receipt.' + fmt.lower(), raw.getvalue(), content_type=mime)
    cleaned = FileUploadValidator.validate_image_file(upload)
    result = Image.open(cleaned)
    assert result.size == (4, 6)
    assert not result.getexif()


@pytest.mark.backend
def test_oversized_upload_rejected_before_read_or_image_parse():
    upload = SimpleUploadedFile('receipt.png', b'placeholder', content_type='image/png')
    upload.size = FileUploadValidator.MAX_FILE_SIZE + 1
    with patch.object(upload.file, 'read', side_effect=AssertionError('must reject before reading')):
        with pytest.raises(ValidationError, match='limit'):
            FileUploadValidator.validate_image_file(upload)


@pytest.mark.backend
def test_native_heic_upload_and_ocr_preparation_round_trip():
    import pillow_heif
    from lib.ocr.ocr_lib import ReceiptOCR

    pillow_heif.register_heif_opener()
    image = Image.new('RGB', (16, 24), 'red')
    raw = BytesIO()
    image.save(raw, format='HEIF')
    upload = SimpleUploadedFile('receipt.heic', raw.getvalue(), content_type='image/heic')
    cleaned = FileUploadValidator.validate_image_file(upload)
    assert Image.open(cleaned).size == (16, 24)
    cleaned.seek(0)
    ocr = ReceiptOCR.__new__(ReceiptOCR)
    processed, mime = ocr._prepare_image(cleaned.read(), 'image/heic')
    assert mime in ('image/heic', 'image/jpeg')
    assert Image.open(BytesIO(processed)).size == (16, 24)
