#!/usr/bin/env python3
"""
Driver script to test OCR library with IMG_6839.HEIC
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ocr_lib import ReceiptOCR, ReceiptData


def test_ocr_with_image(image_path: str):
    """Test OCR with the specified image"""
    
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        logger.error("Please set OPENAI_API_KEY in .env file")
        return False
    
    logger.info(f"Testing OCR with image: {image_path}")
    logger.info("=" * 60)
    
    try:
        # Initialize OCR
        ocr = ReceiptOCR(api_key)
        
        # Process the image
        logger.info("Processing image with OpenAI Vision API...")
        receipt = ocr.process_image(image_path)
        
        # Display results
        logger.info("\n" + "=" * 60)
        logger.info("EXTRACTION RESULTS")
        logger.info("=" * 60)
        
        logger.info(f"Restaurant: {receipt.restaurant_name}")
        logger.info(f"Date: {receipt.date.strftime('%Y-%m-%d')}")
        logger.info(f"Confidence Score: {receipt.confidence_score:.2%}")
        
        logger.info("\nITEMS:")
        logger.info("-" * 40)
        for i, item in enumerate(receipt.items, 1):
            logger.info(f"{i}. {item.name}")
            logger.info(f"   Quantity: {item.quantity} x ${item.unit_price:.2f} = ${item.total_price:.2f}")
        
        logger.info("\nTOTALS:")
        logger.info("-" * 40)
        logger.info(f"Subtotal: ${receipt.subtotal:.2f}")
        logger.info(f"Tax:      ${receipt.tax:.2f}")
        logger.info(f"Tip:      ${receipt.tip:.2f}")
        logger.info(f"TOTAL:    ${receipt.total:.2f}")
        
        # Validate
        logger.info("\nVALIDATION:")
        logger.info("-" * 40)
        is_valid, errors = receipt.validate()
        if is_valid:
            logger.info("✓ Receipt data is valid")
        else:
            logger.warning("✗ Validation issues found:")
            for error in errors:
                logger.warning(f"  - {error}")
        
        # Calculate accuracy metrics
        items_sum = sum(item.total_price for item in receipt.items)
        calculated_total = receipt.subtotal + receipt.tax + receipt.tip
        
        logger.info("\nACCURACY CHECK:")
        logger.info("-" * 40)
        logger.info(f"Items sum:        ${items_sum:.2f}")
        logger.info(f"Receipt subtotal: ${receipt.subtotal:.2f}")
        logger.info(f"Difference:       ${abs(items_sum - receipt.subtotal):.2f}")
        logger.info("")
        logger.info(f"Calculated total: ${calculated_total:.2f}")
        logger.info(f"Receipt total:    ${receipt.total:.2f}")
        logger.info(f"Difference:       ${abs(calculated_total - receipt.total):.2f}")
        
        # Save results to file
        output_file = Path("ocr_test_results.json")
        with open(output_file, 'w') as f:
            json.dump(receipt.to_dict(), f, indent=2, default=str)
        logger.info(f"\n✓ Results saved to {output_file}")
        
        # Save raw response for debugging
        debug_file = Path("ocr_debug_raw.txt")
        with open(debug_file, 'w') as f:
            f.write(receipt.raw_text)
        logger.info(f"✓ Raw OCR response saved to {debug_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Main function"""
    # Test image path
    test_image = "IMG_6839.HEIC"
    
    if not Path(test_image).exists():
        logger.error(f"Test image not found: {test_image}")
        logger.info("Please ensure IMG_6839.HEIC is in the current directory")
        return 1
    
    # Run the test
    logger.info("Starting OCR Test")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    success = test_ocr_with_image(test_image)
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("✓ OCR TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("\n" + "=" * 60)
        logger.error("✗ OCR TEST FAILED")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())