"""
Centralized validation pipeline for all receipt-related validations
Unifies validation logic from validators.py, validation.py, and inline validations
"""
from typing import Dict, Tuple, Optional, Any
from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from receipts.validators import InputValidator, FileUploadValidator
from receipts.validation import validate_receipt_balance


class ValidationPipeline:
    """Centralized validation for all receipt operations"""
    
    @staticmethod
    def round_money(value: Decimal) -> Decimal:
        """Round a decimal value to 2 decimal places"""
        return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def validate_name(self, name: str, field_name: str = "Name") -> str:
        """Validate and sanitize a name field"""
        try:
            return InputValidator.validate_name(name, field_name)
        except ValidationError as e:
            raise ValidationError({field_name.lower().replace(' ', '_'): str(e)})
    
    def validate_image_file(self, image_file: UploadedFile) -> UploadedFile:
        """Validate uploaded image file"""
        if not image_file:
            raise ValidationError({'image': 'Please upload a receipt image'})
        
        if image_file.size == 0:
            raise ValidationError({'image': 'Image file is empty'})
        
        if image_file.size > 10 * 1024 * 1024:
            raise ValidationError({'image': 'Image size must be less than 10MB'})
        
        try:
            return FileUploadValidator.validate_image_file(image_file)
        except ValidationError as e:
            raise ValidationError({'image': str(e)})
    
    def validate_receipt_data(self, data: Dict) -> Tuple[Dict, Dict]:
        """
        Validate receipt data for update operations
        Returns (validated_data, validation_errors)
        Allows saving even with validation errors (business requirement)
        """
        validation_errors = {}
        
        # First pass - input validation
        try:
            validated_data = InputValidator.validate_receipt_data(data)
        except ValidationError as e:
            # Collect input validation errors but don't block
            if hasattr(e, 'message_dict'):
                validation_errors.update(e.message_dict)
            else:
                validation_errors['input'] = str(e)
            validated_data = data  # Use original data if validation fails
        
        # Second pass - balance validation
        is_valid, balance_errors = validate_receipt_balance(validated_data)
        if balance_errors:
            validation_errors.update(balance_errors)
        
        return validated_data, validation_errors
    
    def validate_for_finalization(self, receipt_data: Dict) -> Tuple[bool, Optional[Dict]]:
        """
        Strict validation for receipt finalization
        Receipt must be balanced to be finalized
        """
        # Input validation first
        try:
            validated_data = InputValidator.validate_receipt_data(receipt_data)
        except ValidationError as e:
            errors = {}
            if hasattr(e, 'message_dict'):
                errors.update(e.message_dict)
            elif hasattr(e, 'messages'):
                errors['validation'] = e.messages
            else:
                errors['validation'] = [str(e)]
            return False, errors
        
        # Balance validation - must pass for finalization
        is_valid, balance_errors = validate_receipt_balance(validated_data)
        
        if not is_valid:
            return False, balance_errors
        
        return True, None
    
    def validate_claim_request(self, line_item_id: str, quantity: int, 
                              available_quantity: int) -> Tuple[bool, Optional[str]]:
        """Validate a claim request"""
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        if quantity > available_quantity:
            return False, f"Only {available_quantity} available"
        
        return True, None
    
    def validate_session_context(self, session_data: Dict) -> bool:
        """Validate session context for operations"""
        return bool(session_data.get('session_key'))
    
    def format_validation_errors(self, errors: Dict) -> str:
        """Format validation errors for display"""
        if not errors:
            return ""
        
        error_messages = []
        
        for key, value in errors.items():
            if key == 'items' and isinstance(value, list):
                for item_error in value:
                    if isinstance(item_error, dict) and 'message' in item_error:
                        error_messages.append(f"- {item_error['message']}")
            elif key == 'warnings' and isinstance(value, list):
                # Skip warnings in error formatting
                continue
            elif key != 'warnings':
                if isinstance(value, list):
                    for msg in value:
                        # Handle nested lists (from ValidationError.messages)
                        if isinstance(msg, list):
                            for submsg in msg:
                                error_messages.append(f"- {submsg}")
                        else:
                            error_messages.append(f"- {msg}")
                elif isinstance(value, dict):
                    # Handle nested dicts
                    for subkey, subvalue in value.items():
                        if isinstance(subvalue, list):
                            for msg in subvalue:
                                error_messages.append(f"- {msg}")
                        else:
                            error_messages.append(f"- {subvalue}")
                else:
                    error_messages.append(f"- {value}")
        
        return "\n".join(error_messages)
    
    def extract_warnings(self, errors: Dict) -> list:
        """Extract warnings from validation errors"""
        if not errors or 'warnings' not in errors:
            return []
        
        return errors.get('warnings', [])