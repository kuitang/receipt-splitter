"""
OCR Library for Receipt Processing using Google Gemini API with Pydantic validation
"""

import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Union, BinaryIO

from PIL import Image, ImageOps
import pillow_heif
from google import genai
from google.genai import types

from .models import ReceiptData, LineItem

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Receipt JSON Schema (single source of truth for Gemini structured output)
# ---------------------------------------------------------------------------

RECEIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "restaurant_name": {"type": "string"},
        "date": {"type": "string"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "number"},
                    "total_price": {"type": "number"},
                },
                "required": ["name", "quantity", "unit_price", "total_price"],
                "additionalProperties": False,
            },
        },
        "subtotal": {"type": "number"},
        "tax": {"type": "number"},
        "tip": {"type": "number"},
        "total": {"type": "number"},
        "confidence_score": {"type": "number"},
        "notes": {"type": ["string", "null"]},
    },
    "required": [
        "restaurant_name", "date", "items",
        "subtotal", "tax", "tip", "total",
        "confidence_score", "notes",
    ],
    "additionalProperties": False,
}


def _gemini_schema(schema: dict) -> dict:
    """Convert JSON Schema to Gemini-compatible schema.

    Gemini doesn't support union types like ["string", "null"] or
    additionalProperties. Convert to single types and strip unsupported keys.
    """
    import copy
    s = copy.deepcopy(schema)

    def _fix(node):
        if not isinstance(node, dict):
            return
        # Convert union types to single type (drop null)
        if "type" in node and isinstance(node["type"], list):
            non_null = [t for t in node["type"] if t != "null"]
            node["type"] = non_null[0] if non_null else "string"
            node["nullable"] = True
        # Remove additionalProperties (unsupported by Gemini)
        node.pop("additionalProperties", None)
        # Recurse into properties
        for prop in node.get("properties", {}).values():
            _fix(prop)
        # Recurse into array items
        if "items" in node and isinstance(node["items"], dict):
            _fix(node["items"])

    _fix(s)
    return s


# ---------------------------------------------------------------------------
# Mime type detection
# ---------------------------------------------------------------------------

_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".webp": "image/webp",
}

# Map PIL format names to save kwargs
_PIL_FORMAT_MAP = {
    "JPEG": {"format": "JPEG", "quality": 85},
    "PNG": {"format": "PNG"},
    "WEBP": {"format": "WEBP"},
    "HEIF": {"format": "HEIF"},
}


def _detect_mime(path: Path) -> str:
    """Detect MIME type from file extension."""
    return _MIME_MAP.get(path.suffix.lower(), "image/jpeg")


def _mime_to_pil_format(mime: str) -> str:
    """Convert MIME type to PIL format string."""
    return {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
        "image/heic": "HEIF",
        "image/heif": "HEIF",
    }.get(mime, "JPEG")


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def _calculate_gemini_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate Gemini API cost based on current pricing.

    Gemini 3 Flash pricing:
        Input: $0.50 per 1M tokens
        Output: $3.00 per 1M tokens (non-thinking)
    """
    pricing = {
        "gemini-3-flash-preview": {
            "input_per_1m": 0.50,
            "output_per_1m": 3.00,
        },
        "gemini-3-pro-preview": {
            "input_per_1m": 2.50,
            "output_per_1m": 15.00,
        },
    }

    # Default to flash pricing
    model_pricing = pricing.get(model, pricing["gemini-3-flash-preview"])

    input_cost = (input_tokens / 1_000_000) * model_pricing["input_per_1m"]
    output_cost = (output_tokens / 1_000_000) * model_pricing["output_per_1m"]

    return input_cost + output_cost


class ReceiptOCR:
    """Main OCR class for processing receipt images with Gemini structured output"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        thinking_level: str = "low",
    ):
        """
        Initialize the OCR processor.

        Args:
            api_key: Google Gemini API key
            model: Gemini model to use (default: gemini-3-flash-preview)
            thinking_level: Gemini thinking level (default: low)
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.thinking_level = thinking_level

    def _prepare_image(self, raw_bytes: bytes, mime_type: str) -> tuple:
        """Prepare image bytes: EXIF rotate only, preserve original format.

        Args:
            raw_bytes: Raw image bytes
            mime_type: MIME type of the image

        Returns:
            Tuple of (processed_bytes, mime_type)
        """
        image = Image.open(BytesIO(raw_bytes))

        # Apply EXIF rotation
        try:
            rotated = ImageOps.exif_transpose(image)
            if rotated is not image:
                image = rotated
        except Exception as e:
            logger.debug(f"Could not auto-rotate image: {e}")

        # Save back in original format
        pil_format = _mime_to_pil_format(mime_type)
        save_kwargs = _PIL_FORMAT_MAP.get(pil_format, {"format": "JPEG"})

        buffer = BytesIO()
        try:
            image.save(buffer, **save_kwargs)
            return buffer.getvalue(), mime_type
        except Exception:
            # Fallback: if saving in original format fails (e.g., HEIF write not supported),
            # convert to JPEG
            logger.debug(f"Could not save as {pil_format}, falling back to JPEG")
            buffer = BytesIO()
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            image.save(buffer, format='JPEG', quality=85)
            return buffer.getvalue(), "image/jpeg"

    def _create_prompt(self) -> str:
        """Create the prompt for Gemini Vision API (v5_aligned, hardcoded)"""
        return """Extract receipt data from this image into structured JSON.

ITEM RULES:
1. Extract line items that have a non-zero price. Each item needs: name, quantity, unit_price, total_price.
2. Modifier add-ons WITH a price (e.g., "+AMERICAN CHS 0.75") ARE separate items.
3. Modifier lines WITHOUT a price ("medium", "W/R", "NEAT", "no onions") are NOT items — skip them.
4. Zero-price items ($0.00) are NOT items — skip them (e.g., free toppings like "Lettuce $0.00").
5. Quantity patterns:
   - "2 Lunch 45.90" → qty=2, total_price=45.90, unit_price=22.95
   - "(2 @14.00) 28.00" → qty=2, unit_price=14.00, total_price=28.00
   - "3 ASADA TACO 8.10" → qty=3, total_price=8.10, unit_price=2.70
   - No quantity shown → qty=1
6. total_price MUST equal quantity × unit_price.

TOTALS:
7. subtotal: Sum before tax/tip. Should match sum of item total_prices.
8. tax: Tax amount. Use 0 if not shown.
9. tip: ONLY if actually charged (not suggested tips). Include service charges/fees. Use 0 if not charged.
10. total: Final amount due. If multiple "Total" lines exist, use the LARGEST value.
11. Verify: subtotal + tax + tip ≈ total.

OUTPUT:
12. confidence_score: 0-1 based on extraction certainty.
13. notes: Any ambiguities or issues."""

    def _ocr_api_call(self, image_bytes: bytes, mime_type: str) -> str:
        """Make the Gemini API call for receipt OCR."""
        logger.info(f"Making Gemini API call ({len(image_bytes)} bytes, {mime_type})")

        try:
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": _gemini_schema(RECEIPT_SCHEMA),
            }
            if self.thinking_level:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.thinking_level
                )

            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_text(text=self._create_prompt()),
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(**config_kwargs),
            )

            # Log usage information with cost
            usage_meta = response.usage_metadata
            if usage_meta:
                input_tokens = getattr(usage_meta, "prompt_token_count", 0) or 0
                output_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0
                cost = _calculate_gemini_cost(self.model, input_tokens, output_tokens)
                logger.info(
                    f"Gemini API Call Complete - Model: {self.model}, "
                    f"Input tokens: {input_tokens}, "
                    f"Output tokens: {output_tokens}, "
                    f"Cost: ${cost:.4f}"
                )

            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise ValueError(f"Failed to process image with Gemini: {e}")

    def process_image(self, image_input: Union[str, Path, bytes, BinaryIO]) -> ReceiptData:
        """
        Process a receipt image from any input type

        Args:
            image_input: Can be a file path, Path object, bytes, or file-like object

        Returns:
            ReceiptData object with extracted and validated information
        """
        # Load raw bytes and determine mime type
        if isinstance(image_input, (str, Path)):
            image_path = Path(image_input)
            if not image_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_path}")
            logger.info(f"Processing image file: {image_path}")
            raw_bytes = image_path.read_bytes()
            mime_type = _detect_mime(image_path)
        elif isinstance(image_input, bytes):
            logger.info(f"Processing image from bytes ({len(image_input)} bytes)")
            raw_bytes = image_input
            # Default to JPEG for raw bytes; Gemini handles format detection
            mime_type = "image/jpeg"
        else:
            # File-like object
            logger.info("Processing image from file-like object")
            image_input.seek(0)
            raw_bytes = image_input.read()
            filename = getattr(image_input, 'name', '')
            if filename:
                mime_type = _detect_mime(Path(filename))
            else:
                mime_type = "image/jpeg"

        # EXIF rotate, preserve original format
        processed_bytes, processed_mime = self._prepare_image(raw_bytes, mime_type)

        # Make the API call
        response_text = self._ocr_api_call(processed_bytes, processed_mime)

        # Parse response with Pydantic
        try:
            receipt_data = ReceiptData.model_validate_json(response_text)
        except Exception as e:
            logger.error(f"Failed to parse OCR response: {e}")
            logger.debug(f"Response text: {response_text[:500]}...")
            raise ValueError(f"Failed to parse OCR results: {e}")

        # Validate and correct if needed
        is_valid, errors = receipt_data.validate_totals()
        if not is_valid:
            logger.warning(f"Receipt validation issues: {errors}")
            corrections = receipt_data.correct_totals()
            if corrections['applied']:
                logger.info(f"Applied corrections: {corrections['reason']}")

                # Re-validate after corrections
                is_valid_after, errors_after = receipt_data.validate_totals()
                if is_valid_after:
                    logger.info("Receipt validation successful after corrections")
                else:
                    logger.warning(f"Receipt still has issues after corrections: {errors_after}")

        return receipt_data

    # Backwards compatibility alias
    def process_image_bytes(self, image_bytes: bytes, format: str = "JPEG") -> ReceiptData:
        """Process receipt image from bytes - redirects to unified process_image method"""
        try:
            return self.process_image(image_bytes)
        except Exception as e:
            logger.error(f"Failed to process image bytes: {e}")
            raise

