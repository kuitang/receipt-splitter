import resource
from django.test import TestCase
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO

from receipts.validators import FileUploadValidator


def _make_image(fmt='JPEG', size=(1, 1), mode='RGB', exif=False):
    """Create a small in-memory image in the given format."""
    buf = BytesIO()
    img = Image.new(mode, size, color='white')
    save_kwargs = {}
    if exif and fmt == 'JPEG':
        # Minimal EXIF: just software tag
        import struct
        # Build a tiny EXIF block (APP1 marker)
        exif_bytes = b'Exif\x00\x00'
        # TIFF header (little-endian)
        exif_bytes += b'II'  # little endian
        exif_bytes += struct.pack('<H', 42)  # magic
        exif_bytes += struct.pack('<I', 8)   # offset to IFD
        # IFD with 1 entry: Software tag (0x0131)
        exif_bytes += struct.pack('<H', 1)   # count
        exif_bytes += struct.pack('<HH', 0x0131, 2)  # tag, type=ASCII
        exif_bytes += struct.pack('<I', 5)   # count of chars
        exif_bytes += b'Test\x00'            # value (inline, <=4 bytes needs padding)
        exif_bytes += struct.pack('<I', 0)   # next IFD offset
        save_kwargs['exif'] = exif_bytes
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def _make_uploaded(content, name='test.jpg', content_type='image/jpeg'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class FileUploadValidatorTests(TestCase):
    """Core validator tests."""

    def test_valid_jpeg(self):
        f = _make_uploaded(_make_image('JPEG'))
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

    def test_valid_png(self):
        f = _make_uploaded(_make_image('PNG'), name='test.png', content_type='image/png')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

    def test_valid_webp(self):
        f = _make_uploaded(_make_image('WEBP'), name='test.webp', content_type='image/webp')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

    def test_empty_file(self):
        f = _make_uploaded(b'', name='empty.jpg')
        f.size = 0
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_no_file(self):
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(None)

    def test_oversized_file(self):
        f = _make_uploaded(b'\x00' * 100, name='big.jpg')
        f.size = 11 * 1024 * 1024  # 11MB
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)


class MislabeledFileTests(TestCase):
    """Files with wrong extensions should be validated by content, not name."""

    def test_jpeg_with_heic_extension(self):
        """A JPEG file named .heic should pass (magic detects image/jpeg)."""
        content = _make_image('JPEG')
        f = _make_uploaded(content, name='photo.heic', content_type='image/heic')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

    def test_png_with_jpg_extension(self):
        """A PNG file named .jpg should pass (magic detects image/png)."""
        content = _make_image('PNG')
        f = _make_uploaded(content, name='image.jpg', content_type='image/jpeg')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

    def test_webp_with_png_extension(self):
        """A WebP file named .png should pass (magic detects image/webp)."""
        content = _make_image('WEBP')
        f = _make_uploaded(content, name='image.png', content_type='image/png')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)


class JunkFileTests(TestCase):
    """Junk, corrupt, and non-image files must be rejected."""

    def test_random_bytes(self):
        """Random bytes should be rejected."""
        f = _make_uploaded(b'\x00\x01\x02\x03\x04\x05' * 100, name='junk.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_text_file_as_image(self):
        """A text file named .jpg should be rejected."""
        f = _make_uploaded(b'Hello, this is not an image!', name='fake.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_html_as_image(self):
        """HTML content named .jpg should be rejected."""
        f = _make_uploaded(b'<html><body>XSS</body></html>', name='xss.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_pdf_as_image(self):
        """A PDF file named .jpg should be rejected."""
        f = _make_uploaded(b'%PDF-1.4 fake pdf content', name='receipt.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_truncated_jpeg(self):
        """A JPEG with only a header but truncated body should be rejected."""
        # JPEG SOI marker + truncated
        f = _make_uploaded(b'\xff\xd8\xff\xe0\x00\x10JFIF', name='truncated.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)

    def test_zip_as_image(self):
        """A ZIP file should be rejected regardless of extension."""
        f = _make_uploaded(b'PK\x03\x04' + b'\x00' * 100, name='archive.jpg')
        with self.assertRaises(ValidationError):
            FileUploadValidator.validate_image_file(f)


class ExifStrippingTests(TestCase):
    """EXIF stripping must work without excessive memory usage."""

    def test_exif_stripped_from_jpeg(self):
        """JPEG with EXIF should have EXIF removed after validation."""
        content = _make_image('JPEG', size=(100, 100), exif=True)
        f = _make_uploaded(content, name='exif.jpg')
        result = FileUploadValidator.validate_image_file(f)
        result.seek(0)
        # Re-open and check EXIF is gone (empty dict or None both mean no EXIF)
        img = Image.open(result)
        exif = img._getexif() if hasattr(img, '_getexif') else None
        self.assertFalse(exif, f"EXIF should be empty or None after stripping, got {exif}")

    def test_exif_stripping_memory_efficient(self):
        """EXIF stripping on a large image should not use excessive memory.

        The old approach (list(image.getdata())) used ~2GB for a 12MP image.
        The new approach (info.pop + re-save) should use <200MB.
        """
        # Create a moderately large JPEG with EXIF (2000x2000 = 4MP)
        content = _make_image('JPEG', size=(2000, 2000), exif=True)
        f = _make_uploaded(content, name='large.jpg')

        # Get baseline memory
        before_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)

        after_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Memory increase should be well under 500MB (was 2GB+ before fix)
        delta_mb = (after_maxrss - before_maxrss) / 1024
        self.assertLess(delta_mb, 500,
                        f"EXIF stripping used {delta_mb:.0f}MB — too much memory")

    def test_no_exif_passthrough(self):
        """JPEG without EXIF should pass through without re-encoding."""
        content = _make_image('JPEG', size=(100, 100))
        f = _make_uploaded(content, name='no_exif.jpg')
        result = FileUploadValidator.validate_image_file(f)
        self.assertIsNotNone(result)


class SafeFilenameTests(TestCase):
    """generate_safe_filename should use magic, not extensions."""

    def test_filename_extension_from_content(self):
        """Extension should match detected content type, not original name."""
        # PNG content with .heic name
        content = _make_image('PNG')
        f = _make_uploaded(content, name='photo.heic', content_type='image/heic')
        filename = FileUploadValidator.generate_safe_filename(f)
        self.assertTrue(filename.endswith('.png'),
                        f"Expected .png extension for PNG content, got {filename}")

    def test_filename_jpeg_content(self):
        content = _make_image('JPEG')
        f = _make_uploaded(content, name='x.png', content_type='image/png')
        filename = FileUploadValidator.generate_safe_filename(f)
        self.assertTrue(filename.endswith('.jpg'),
                        f"Expected .jpg extension, got {filename}")

    def test_filename_webp_content(self):
        content = _make_image('WEBP')
        f = _make_uploaded(content, name='y.jpg', content_type='image/jpeg')
        filename = FileUploadValidator.generate_safe_filename(f)
        self.assertTrue(filename.endswith('.webp'),
                        f"Expected .webp extension, got {filename}")


class MagicDetectionTests(TestCase):
    """_detect_mime_type must always use libmagic."""

    def test_detect_jpeg(self):
        content = _make_image('JPEG')
        mime = FileUploadValidator._detect_mime_type(content)
        self.assertEqual(mime, 'image/jpeg')

    def test_detect_png(self):
        content = _make_image('PNG')
        mime = FileUploadValidator._detect_mime_type(content)
        self.assertEqual(mime, 'image/png')

    def test_detect_webp(self):
        content = _make_image('WEBP')
        mime = FileUploadValidator._detect_mime_type(content)
        self.assertEqual(mime, 'image/webp')

    def test_detect_text_not_image(self):
        mime = FileUploadValidator._detect_mime_type(b'Hello world')
        self.assertNotIn(mime, FileUploadValidator.ALLOWED_MIME_TYPES)

    def test_magic_exception_raises_validation_error(self):
        with patch('receipts.validators.magic.from_buffer', side_effect=Exception("boom")):
            with self.assertRaises(ValidationError):
                FileUploadValidator._detect_mime_type(b'anything')


class PillowFailureTests(TestCase):
    """PIL/Pillow failures should raise ValidationError, not crash."""

    def test_pillow_open_failure(self):
        f = _make_uploaded(_make_image('JPEG'))
        with patch.object(FileUploadValidator, '_detect_mime_type', return_value='image/jpeg'):
            with patch('receipts.validators.Image.open', side_effect=Exception("PIL failed")):
                with self.assertRaises(ValidationError):
                    FileUploadValidator.validate_image_file(f)

    def test_detect_mime_exception_in_validate(self):
        f = _make_uploaded(_make_image('JPEG'))
        with patch.object(FileUploadValidator, '_detect_mime_type', side_effect=Exception("boom")):
            with self.assertRaises(ValidationError):
                FileUploadValidator.validate_image_file(f)
