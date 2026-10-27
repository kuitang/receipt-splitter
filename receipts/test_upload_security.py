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
@pytest.mark.parametrize('fmt,mime', [('png', 'image/png'), ('heic', 'image/heic')])
def test_oversized_upload_rejected_before_read_or_image_parse(fmt, mime):
    upload = SimpleUploadedFile('receipt.' + fmt, b'placeholder', content_type=mime)
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
    exif = Image.Exif()
    exif[0x010E] = 'private receipt HEIC metadata'
    image.save(raw, format='HEIF', exif=exif)
    upload = SimpleUploadedFile('receipt.heic', raw.getvalue(), content_type='image/heic')
    cleaned = FileUploadValidator.validate_image_file(upload)
    assert Image.open(cleaned).size == (16, 24)
    assert not Image.open(cleaned).getexif()
    cleaned.seek(0)
    ocr = ReceiptOCR.__new__(ReceiptOCR)
    processed, mime = ocr._prepare_image(cleaned.read(), 'image/heic')
    assert mime in ('image/heic', 'image/jpeg')
    assert Image.open(BytesIO(processed)).size == (16, 24)


def _heif_box(kind, payload=b'', length_mode='normal'):
    if length_mode == 'extended':
        return (1).to_bytes(4, 'big') + kind + (16 + len(payload)).to_bytes(8, 'big') + payload
    size = 0 if length_mode == 'to_end' else 8 + len(payload)
    return size.to_bytes(4, 'big') + kind + payload


@pytest.mark.backend
@pytest.mark.parametrize('length_mode', ['normal', 'extended', 'to_end'])
def test_heif_sequence_rejected_before_native_parse(length_mode):
    content = _heif_box(b'ftyp', b'heic\x00\x00\x00\x00mif1heic') + _heif_box(b'moov', length_mode=length_mode)
    upload = SimpleUploadedFile('receipt.heic', content, content_type='image/heic')
    with patch.object(FileUploadValidator, '_detect_mime_type', return_value='image/heic'):
        with patch('receipts.validators.Image.open', side_effect=AssertionError('must reject before native parsing')):
            with pytest.raises(ValidationError, match='sequences'):
                FileUploadValidator.validate_image_file(upload)


@pytest.mark.backend
@pytest.mark.parametrize('tail', [
    b'\x00' * 7,
    (1).to_bytes(4, 'big') + b'free' + b'\x00' * 7,
    (1).to_bytes(4, 'big') + b'free' + (2**64 - 1).to_bytes(8, 'big'),
    (7).to_bytes(4, 'big') + b'free',
    (1).to_bytes(4, 'big') + b'free' + (15).to_bytes(8, 'big'),
    (32).to_bytes(4, 'big') + b'free' + b'short',
])
def test_malformed_heif_box_lengths_rejected_before_native_parse(tail):
    content = _heif_box(b'ftyp', b'heic\x00\x00\x00\x00mif1heic') + tail
    upload = SimpleUploadedFile('receipt.heic', content, content_type='image/heic')
    with patch.object(FileUploadValidator, '_detect_mime_type', return_value='image/heic'):
        with patch('receipts.validators.Image.open', side_effect=AssertionError('must reject before native parsing')):
            with pytest.raises(ValidationError, match='length'):
                FileUploadValidator.validate_image_file(upload)


@pytest.mark.backend
def test_heif_top_level_box_count_is_bounded_before_native_parse():
    content = _heif_box(b'ftyp', b'heic\x00\x00\x00\x00mif1heic')
    content += _heif_box(b'free') * FileUploadValidator.MAX_HEIF_TOP_LEVEL_BOXES
    upload = SimpleUploadedFile('receipt.heic', content, content_type='image/heic')
    with patch.object(FileUploadValidator, '_detect_mime_type', return_value='image/heic'):
        with patch('receipts.validators.Image.open', side_effect=AssertionError('must reject before native parsing')):
            with pytest.raises(ValidationError, match='too many'):
                FileUploadValidator.validate_image_file(upload)


@pytest.mark.backend
@pytest.mark.parametrize('length_mode', ['normal', 'extended', 'to_end'])
def test_real_still_heic_with_moov_bytes_in_padding_preserves_stream(length_mode):
    import pillow_heif

    pillow_heif.register_heif_opener()
    raw = BytesIO()
    Image.new('RGB', (16, 24), 'red').save(raw, format='HEIF')
    content = raw.getvalue() + _heif_box(b'free', b'moov is harmless inside a padding box', length_mode)
    upload = SimpleUploadedFile('receipt.heic', content, content_type='image/heic')
    upload.seek(7)
    cleaned = FileUploadValidator.validate_image_file(upload)
    assert cleaned.tell() == 0
    assert Image.open(cleaned).size == (16, 24)
