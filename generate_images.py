#!/usr/bin/env python3
"""
Generate sample images for the Communist Style receipt splitter app
using OpenAI's DALL-E image generation API.
"""

import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "receipt_splitter.settings")
django.setup()

from openai import OpenAI
from django.conf import settings
import requests
from datetime import datetime


def generate_and_save_images():
    """Generate sample images showing diverse groups enjoying activities"""
    
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_api_key_here":
        print("Please set OPENAI_API_KEY in .env file")
        return
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    image_prompts = [
        {
            "prompt": "Illustrative, vibrant artwork of a diverse group of 5 friends at a restaurant table with a receipt and calculator in the center, everyone pointing at different items on the bill, warm lighting, collaborative and friendly atmosphere, modern flat design style",
            "filename": "hero_split_receipt.png",
            "caption": "Friends splitting a restaurant receipt"
        },
        {
            "prompt": "Illustrative, colorful artwork of a diverse group of 4 people at a dinner table, one person holding up a smartphone showing a split bill app, others looking pleased, restaurant setting with warm ambient lighting, modern illustration style",
            "filename": "hero_mobile_split.png", 
            "caption": "Using technology to split bills fairly"
        },
        {
            "prompt": "Illustrative artwork of hands from different people pointing at items on a restaurant receipt, calculator and phones visible, top-down view, bright and clean design, emphasizing collaboration and fairness",
            "filename": "hero_collaborative.png",
            "caption": "Collaborative bill splitting"
        },
        {
            "prompt": "Illustrative, cheerful artwork of a diverse group enjoying dinner at a long table, receipt paper trail winding between plates, everyone smiling and engaged, warm restaurant atmosphere, modern flat illustration style",
            "filename": "group_dinner.png",
            "caption": "Group dinner with easy bill splitting"
        },
        {
            "prompt": "Illustrative artwork of a receipt transforming into individual smaller receipts with colorful arrows, abstract and modern design, bright colors on white background, clean minimalist style",
            "filename": "receipt_transform.png",
            "caption": "Receipt splitting visualization"
        },
        {
            "prompt": "Illustrative artwork of diverse friends high-fiving after dinner, empty plates and a neatly divided receipt on the table, celebration atmosphere, warm evening light, joyful and inclusive scene",
            "filename": "success_split.png",
            "caption": "Successfully split the bill"
        }
    ]
    
    media_dir = Path("media/sample_images")
    media_dir.mkdir(parents=True, exist_ok=True)
    
    prompts_file = media_dir / "prompts.txt"
    
    with open(prompts_file, "w") as f:
        f.write(f"Generated on: {datetime.now()}\n\n")
        
        for i, image_data in enumerate(image_prompts, 1):
            print(f"Generating image {i}/{len(image_prompts)}: {image_data['caption']}")
            
            try:
                response = client.images.generate(
                    model="dall-e-2",
                    prompt=image_data["prompt"],
                    size="1024x1024",
                    n=1,
                )
                
                image_url = response.data[0].url
                
                img_response = requests.get(image_url)
                if img_response.status_code == 200:
                    image_path = media_dir / image_data["filename"]
                    with open(image_path, "wb") as img_file:
                        img_file.write(img_response.content)
                    
                    print(f"  ✓ Saved to {image_path}")
                    
                    f.write(f"Image {i}: {image_data['filename']}\n")
                    f.write(f"Caption: {image_data['caption']}\n")
                    f.write(f"Prompt: {image_data['prompt']}\n")
                    f.write(f"URL: {image_url}\n\n")
                else:
                    print(f"  ✗ Failed to download image")
                    
            except Exception as e:
                print(f"  ✗ Error generating image: {e}")
    
    print(f"\nPrompts saved to: {prompts_file}")
    print("Images generated successfully!")


if __name__ == "__main__":
    generate_and_save_images()