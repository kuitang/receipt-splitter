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
            "prompt": "Simple, clean illustration of a smartphone camera scanning a restaurant receipt, flat design style, bright colors, minimalist, white background with subtle blue accents",
            "filename": "step_upload.png",
            "caption": "Upload receipt step"
        },
        {
            "prompt": "Simple, clean illustration of a hand holding a smartphone with a share icon and link being sent to multiple contacts, flat design style, bright colors, minimalist, white background with subtle blue accents",
            "filename": "step_share.png", 
            "caption": "Share link step"
        },
        {
            "prompt": "Simple, clean illustration of multiple smartphones showing individual payment amounts with checkmarks, representing fair bill splitting, flat design style, bright colors, minimalist, white background with subtle blue accents",
            "filename": "step_split.png",
            "caption": "Split fairly step"
        },
        {
            "prompt": "Cheerful, simple illustration of diverse hands giving thumbs up around a receipt marked 'PAID', celebration of successful bill split, flat design style, bright colors, minimalist",
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
                    model="dall-e-3",
                    prompt=image_data["prompt"],
                    size="1024x1024",
                    quality="standard",
                    style="natural",
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