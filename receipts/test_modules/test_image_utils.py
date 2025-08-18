from django.test import TestCase
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile

from receipts.image_utils import convert_to_jpeg_if_needed

class ImageUtilsTests(TestCase):
    @patch('receipts.image_utils.Image.open')
    def test_convert_to_jpeg_if_needed_exception(self, mock_image_open):
        """Test that an exception during conversion is handled correctly."""
        mock_image_open.side_effect = Exception("Conversion failed")

        heic_file = SimpleUploadedFile("test.heic", b"file_content", content_type="image/heic")

        with self.assertLogs('receipts.image_utils', level='ERROR') as cm:
            with self.assertRaisesMessage(ValueError, 'Failed to process HEIC file.'):
                convert_to_jpeg_if_needed(heic_file)
            self.assertIn("Failed to convert HEIC file", cm.output[0])
