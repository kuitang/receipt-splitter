import base64
import json
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from PIL import Image
from openai import OpenAI
from django.conf import settings


def process_receipt_with_ocr(image_file):
    """
    Process receipt image using OpenAI Vision API to extract structured data
    
    For development/testing, returns mock data if OpenAI API key is not configured
    """
    
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_api_key_here":
        return get_mock_receipt_data()
    
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        image = Image.open(image_file)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        buffer = BytesIO()
        image.save(buffer, format='JPEG', quality=85)
        image_data = buffer.getvalue()
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        prompt = """Analyze this receipt image and extract the following information in JSON format:
        {
            "restaurant_name": "string",
            "date": "YYYY-MM-DD HH:MM:SS",
            "items": [
                {
                    "name": "string",
                    "quantity": integer,
                    "unit_price": number,
                    "total_price": number
                }
            ],
            "subtotal": number,
            "tax": number,
            "tip": number,
            "total": number
        }
        
        Important:
        - Extract all line items with their quantities and prices
        - If quantity is not specified, assume 1
        - Ensure subtotal + tax + tip = total
        - All monetary values should be in dollars with 2 decimal places
        - If date is not visible, use today's date
        - If tip is not shown, set it to 0
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.1
        )
        
        result_text = response.choices[0].message.content
        
        json_start = result_text.find('{')
        json_end = result_text.rfind('}') + 1
        if json_start != -1 and json_end != 0:
            result_text = result_text[json_start:json_end]
        
        data = json.loads(result_text)
        
        if isinstance(data['date'], str):
            try:
                data['date'] = datetime.strptime(data['date'], '%Y-%m-%d %H:%M:%S')
            except:
                try:
                    data['date'] = datetime.strptime(data['date'], '%Y-%m-%d')
                except:
                    data['date'] = datetime.now()
        
        return data
        
    except Exception as e:
        print(f"OCR Error: {str(e)}")
        return get_mock_receipt_data()


def get_mock_receipt_data():
    """Return mock receipt data for testing"""
    return {
        "restaurant_name": "Demo Restaurant",
        "date": datetime.now(),
        "items": [
            {
                "name": "Burger",
                "quantity": 1,
                "unit_price": 12.99,
                "total_price": 12.99
            },
            {
                "name": "Fries",
                "quantity": 2,
                "unit_price": 3.99,
                "total_price": 7.98
            },
            {
                "name": "Soda",
                "quantity": 2,
                "unit_price": 2.99,
                "total_price": 5.98
            },
            {
                "name": "Salad",
                "quantity": 1,
                "unit_price": 8.99,
                "total_price": 8.99
            }
        ],
        "subtotal": 35.94,
        "tax": 3.24,
        "tip": 6.00,
        "total": 45.18
    }