"""
Input validators for receipt application
Provides comprehensive validation for file uploads and user inputs
"""

from django.core.exceptions import ValidationError
from PIL import Image
import logging
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO

import bleach
import magic

logger = logging.getLogger(__name__)


class FileUploadValidator:
    """Validate uploaded image files for security and requirements"""
    
    ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def validate_image_file(cls, uploaded_file):
        """
        Comprehensive image file validation
        Returns: cleaned file ready for processing
        Raises: ValidationError if file is invalid
        """
        # Check file exists and has content
        if not uploaded_file:
            raise ValidationError('No file provided')
        
        # Check file size
        if uploaded_file.size == 0:
            raise ValidationError('File is empty')
        
        if uploaded_file.size > cls.MAX_FILE_SIZE:
            raise ValidationError(f'File size exceeds {cls.MAX_FILE_SIZE/1024/1024}MB limit')
        
        # Read file content for validation
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        uploaded_file.seek(0)
        
        try:
            detected_mime = cls._detect_mime_type(file_content)
        except ValidationError:
            raise
        except Exception:
            logger.exception("Unable to determine file type")
            raise ValidationError('Unable to determine file type.')

        if detected_mime not in cls.ALLOWED_MIME_TYPES:
            raise ValidationError(f'File content is not a valid image. Detected type: {detected_mime}')
        
        # Additional image validation
        try:
            # Try to open and verify it's a valid image
            image = Image.open(BytesIO(file_content))
            image.verify()  # Verify it's a valid image
            
            # Re-open for dimension check (verify() closes the file)
            uploaded_file.seek(0)
            image = Image.open(uploaded_file)
            
            # No dimension restrictions - support all image sizes
            
            # Strip EXIF data for privacy (removes GPS location, etc.)
            # Previous approach used list(image.getdata()) which created
            # ~12M Python tuples for a 12MP image, consuming ~2GB RAM.
            # Instead, just remove EXIF from the info dict and re-save.
            if hasattr(image, '_getexif') and image._getexif():
                image.info.pop('exif', None)
                output = BytesIO()
                image_format = image.format or 'JPEG'
                save_kwargs = {}
                if image_format == 'JPEG':
                    save_kwargs['quality'] = 95
                # Preserve ICC color profile if present
                icc = image.info.get('icc_profile')
                if icc:
                    save_kwargs['icc_profile'] = icc
                image.save(output, format=image_format, **save_kwargs)
                output.seek(0)

                # Update the uploaded file
                uploaded_file.file = output
                uploaded_file.size = output.getbuffer().nbytes
                
        except Exception as e:
            logger.exception("Invalid image file")
            raise ValidationError('Invalid image file.')
        
        uploaded_file.seek(0)
        return uploaded_file

    @classmethod
    def _detect_mime_type(cls, file_content):
        """Detect MIME type using libmagic."""
        try:
            return magic.from_buffer(file_content, mime=True)
        except Exception as exc:
            logger.exception("libmagic failed to detect file type")
            raise ValidationError('Unable to determine file type.') from exc
    
    MIME_TO_EXTENSION = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/heic': 'heic',
        'image/heif': 'heif',
    }

    @classmethod
    def generate_safe_filename(cls, uploaded_file):
        """Generate a secure filename based on file content hash and detected MIME type."""
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        uploaded_file.seek(0)

        file_hash = hashlib.sha256(file_content).hexdigest()[:16]

        # Determine extension from actual content, not the user-supplied filename
        detected_mime = magic.from_buffer(file_content, mime=True)
        extension = cls.MIME_TO_EXTENSION.get(detected_mime, 'jpg')

        from django.utils import timezone
        timestamp = int(timezone.now().timestamp())
        return f"receipt_{file_hash}_{timestamp}.{extension}"


class InputValidator:
    """Validate and sanitize user text inputs"""
    
    @staticmethod
    def validate_name(name, field_name="Name", min_length=2, max_length=50):
        """Validate and sanitize name input"""
        if not name or not isinstance(name, str):
            raise ValidationError(f"{field_name} is required")
        
        # Strip whitespace
        name = name.strip()
        
        # Remove any HTML tags and dangerous characters using bleach
        name = bleach.clean(name, tags=[], strip=True)
        
        # Check length after cleaning
        if len(name) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters")
        
        if len(name) > max_length:
            raise ValidationError(f"{field_name} must not exceed {max_length} characters")
        
        # Check for suspicious patterns (expanded list for security)
        suspicious_patterns = [
            '<script', 'javascript:', 'onclick', 'onerror', 'onload',
            'alert(', 'eval(', 'document.', 'window.', 'console.',
            '<iframe', '<embed', '<object', '<img', '<svg',
            '\x00', '../', '..\\', 'onfocus', 'onmouse'
        ]
        for pattern in suspicious_patterns:
            if pattern.lower() in name.lower():
                raise ValidationError(f"{field_name} contains invalid characters")
        
        # Return the cleaned name without HTML escaping
        # Django templates will handle escaping on output
        return name
    
    @staticmethod
    def validate_decimal(value, field_name="Value", max_digits=12, decimal_places=6, allow_negative=False):
        """Validate decimal values for prices"""
        try:
            if value is None:
                raise ValidationError(f"{field_name} is required")
            
            decimal_value = Decimal(str(value))
            
            # Check for negative values
            if not allow_negative and decimal_value < 0:
                raise ValidationError(f"{field_name} cannot be negative")
            
            # Check precision
            if decimal_value.as_tuple().exponent < -decimal_places:
                raise ValidationError(f"{field_name} has too many decimal places (max {decimal_places})")
            
            # Check magnitude
            max_value = Decimal('9' * (max_digits - decimal_places))
            if abs(decimal_value) > max_value:
                raise ValidationError(f"{field_name} is too large")
            
            # Check for special values
            if not decimal_value.is_finite():
                raise ValidationError(f"{field_name} must be a valid number")
            
            return decimal_value
            
        except (InvalidOperation, TypeError) as e:
            raise ValidationError(f"Invalid {field_name.lower()}: must be a valid number")
    
    @staticmethod
    def validate_quantity(value, field_name="Quantity", min_value=1, max_value=999):
        """Validate quantity values"""
        try:
            qty = int(value)
            if qty < min_value or qty > max_value:
                raise ValidationError(f"{field_name} must be between {min_value} and {max_value}")
            return qty
        except (ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name.lower()}: must be a whole number")
    
    @staticmethod
    def validate_receipt_data(data):
        """Validate complete receipt data structure"""
        errors = []
        
        # Always clean restaurant name, even if validation fails
        original_name = data.get('restaurant_name', '')
        cleaned_name = bleach.clean(original_name, tags=[], strip=True).strip()
        
        try:
            data['restaurant_name'] = InputValidator.validate_name(
                original_name,
                field_name="Restaurant name",
                max_length=100
            )
        except ValidationError as e:
            # Use cleaned name even on validation error
            data['restaurant_name'] = cleaned_name
            # Extract the actual message, not the string representation
            if hasattr(e, 'messages') and e.messages:
                errors.extend(e.messages)
            elif hasattr(e, 'message'):
                errors.append(e.message)
            else:
                errors.append(str(e).strip("[]'\""))
        
        # Validate monetary fields
        for field in ['subtotal', 'tax', 'tip', 'total']:
            try:
                data[field] = InputValidator.validate_decimal(
                    data.get(field, 0),
                    field_name=field.capitalize(),
                    allow_negative=(field in ['tax', 'tip'])  # Allow negative for discounts
                )
            except ValidationError as e:
                # Extract the actual message, not the string representation
                if hasattr(e, 'messages') and e.messages:
                    errors.extend(e.messages)
                elif hasattr(e, 'message'):
                    errors.append(e.message)
                else:
                    errors.append(str(e).strip("[]'\""))
        
        # Validate items
        if 'items' in data:
            for i, item in enumerate(data.get('items', [])):
                # Always clean item name, even if validation fails
                original_item_name = item.get('name', '')
                cleaned_item_name = bleach.clean(original_item_name, tags=[], strip=True).strip()
                
                try:
                    item['name'] = InputValidator.validate_name(
                        original_item_name,
                        field_name=f"Item {i+1} name",
                        max_length=100
                    )
                except ValidationError as e:
                    # Use cleaned name even on validation error
                    item['name'] = cleaned_item_name
                    # Extract the actual message, not the string representation
                    if hasattr(e, 'messages') and e.messages:
                        errors.extend(e.messages)
                    elif hasattr(e, 'message'):
                        errors.append(e.message)
                    else:
                        errors.append(str(e).strip("[]'\""))
                
                # Validate fractional quantity fields
                try:
                    item['quantity_numerator'] = InputValidator.validate_quantity(
                        item.get('quantity_numerator', item.get('quantity', 1)),
                        field_name=f"Item {i+1} quantity numerator"
                    )
                except ValidationError as e:
                    if hasattr(e, 'messages') and e.messages:
                        errors.extend(e.messages)
                    elif hasattr(e, 'message'):
                        errors.append(e.message)
                    else:
                        errors.append(str(e).strip("[]'\""))
                try:
                    item['quantity_denominator'] = InputValidator.validate_quantity(
                        item.get('quantity_denominator', 1),
                        field_name=f"Item {i+1} quantity denominator"
                    )
                except ValidationError as e:
                    if hasattr(e, 'messages') and e.messages:
                        errors.extend(e.messages)
                    elif hasattr(e, 'message'):
                        errors.append(e.message)
                    else:
                        errors.append(str(e).strip("[]'\""))
                
                try:
                    item['unit_price'] = InputValidator.validate_decimal(
                        item.get('unit_price', 0),
                        field_name=f"Item {i+1} price"
                    )
                except ValidationError as e:
                    if hasattr(e, 'messages') and e.messages:
                        errors.extend(e.messages)
                    elif hasattr(e, 'message'):
                        errors.append(e.message)
                    else:
                        errors.append(str(e).strip("[]'\""))
                        
                try:
                    item['total_price'] = InputValidator.validate_decimal(
                        item.get('total_price', 0),
                        field_name=f"Item {i+1} total"
                    )
                except ValidationError as e:
                    if hasattr(e, 'messages') and e.messages:
                        errors.extend(e.messages)
                    elif hasattr(e, 'message'):
                        errors.append(e.message)
                    else:
                        errors.append(str(e).strip("[]'\""))
        
        if errors:
            raise ValidationError(errors)
        
        return data