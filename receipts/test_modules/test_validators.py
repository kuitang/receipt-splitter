from django.test import TestCase
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from receipts.validators import FileUploadValidator

class ValidatorTests(TestCase):
    @patch('receipts.validators.magic.from_buffer')
    def test_validate_image_file_magic_exception(self, mock_from_buffer):
        """Test that an exception from magic is handled correctly."""
        mock_from_buffer.side_effect = Exception("Magic failed")

        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")

        with self.assertLogs('receipts.validators', level='ERROR') as cm:
            with self.assertRaisesMessage(ValidationError, 'Unable to determine file type.'):
                FileUploadValidator.validate_image_file(image)
            self.assertIn("Unable to determine file type", cm.output[0])

    @patch('receipts.validators.magic.from_buffer', return_value='image/jpeg')
    @patch('receipts.validators.Image.open')
    def test_validate_image_file_pil_exception(self, mock_image_open, mock_from_buffer):
        """Test that an exception from PIL is handled correctly."""
        mock_image_open.side_effect = Exception("PIL failed")

        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")

        with self.assertLogs('receipts.validators', level='ERROR') as cm:
            with self.assertRaisesMessage(ValidationError, 'Invalid image file.'):
                FileUploadValidator.validate_image_file(image)
            self.assertIn("Invalid image file", cm.output[0])
