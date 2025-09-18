from django.test import TestCase
from unittest import skipUnless
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from receipts import validators
from receipts.validators import FileUploadValidator


class FileUploadValidatorTests(TestCase):
    def _simple_image(self):
        """Create a tiny in-memory JPEG image for testing."""
        from PIL import Image
        from io import BytesIO

        buffer = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(buffer, format="JPEG")
        return SimpleUploadedFile("test.jpg", buffer.getvalue(), content_type="image/jpeg")

    def test_detect_mime_exception_is_reported(self):
        image = self._simple_image()

        with patch.object(FileUploadValidator, '_detect_mime_type', side_effect=Exception("boom")):
            with self.assertLogs('receipts.validators', level='ERROR') as logs:
                with self.assertRaisesMessage(ValidationError, 'Unable to determine file type.'):
                    FileUploadValidator.validate_image_file(image)
            self.assertTrue(any('Unable to determine file type' in message for message in logs.output))

    @skipUnless(validators.magic is not None, "libmagic unavailable")
    def test_magic_failure_bubbles_as_validation_error(self):
        image = self._simple_image()

        with patch('receipts.validators.magic.from_buffer', side_effect=Exception("Magic failed")):
            with self.assertLogs('receipts.validators', level='ERROR') as logs:
                with self.assertRaisesMessage(ValidationError, 'Unable to determine file type.'):
                    FileUploadValidator.validate_image_file(image)
            self.assertTrue(any('libmagic failed' in message or 'Unable to determine file type' in message for message in logs.output))

    def test_pillow_failure_raises_validation_error(self):
        image = self._simple_image()

        with patch.object(FileUploadValidator, '_detect_mime_type', return_value='image/jpeg'):
            with patch('receipts.validators.Image.open') as mock_image_open:
                mock_image_open.side_effect = Exception("PIL failed")

                with self.assertLogs('receipts.validators', level='ERROR') as logs:
                    with self.assertRaisesMessage(ValidationError, 'Invalid image file.'):
                        FileUploadValidator.validate_image_file(image)

                self.assertTrue(any('Invalid image file' in message for message in logs.output))

