from django.test import TestCase
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

from receipts.image_utils import convert_to_jpeg_if_needed


class ImageUtilsTests(TestCase):
    @patch('receipts.image_utils.detect_mime', return_value='image/heic')
    @patch('receipts.image_utils.Image.open')
    def test_convert_to_jpeg_if_needed_exception(self, mock_image_open, _mock_mime):
        """Test that an exception during conversion raises ValueError."""
        mock_image_open.side_effect = Exception("Conversion failed")

        heic_file = SimpleUploadedFile("test.heic", b"fake_heic_content", content_type="image/heic")

        with self.assertLogs('receipts.image_utils', level='ERROR') as cm:
            with self.assertRaisesMessage(ValueError, 'Failed to process HEIC file.'):
                convert_to_jpeg_if_needed(heic_file)
            self.assertIn("Failed to convert HEIC file", cm.output[0])

    def test_non_heic_passthrough(self):
        """Files that are not HEIC (by content, not extension) pass through unchanged."""
        # JPEG content with .heic extension — magic detects JPEG, not HEIC
        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100
        fake_heic = SimpleUploadedFile("mislabeled.heic", jpeg_bytes, content_type="image/heic")

        result = convert_to_jpeg_if_needed(fake_heic)
        # Should be the same object (not converted) since content is JPEG
        self.assertIs(result, fake_heic)

    def test_none_passthrough(self):
        """None input returns None."""
        result = convert_to_jpeg_if_needed(None)
        self.assertIsNone(result)
