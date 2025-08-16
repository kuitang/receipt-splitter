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
    """Generate sample images showing conventionally attractive groups enjoying activities"""
    
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your_api_key_here":
        print("Please set OPENAI_API_KEY in .env file")
        return
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Watercolor impressionistic style like Manet
    style_prefix = "Watercolor impressionistic painting in the style of Édouard Manet, soft brushstrokes, muted pastel colors, natural light and shadow, "
    
    image_prompts = [
        {
            "prompt": style_prefix + "conventionally attractive group of friends at a café table with a receipt and pencil, loose gestural marks, Parisian café atmosphere, dappled sunlight through windows",
            "filename": "hero_image",
            "caption": "Hero Image - Friends at Café"
        },
        {
            "prompt": style_prefix + "people gathered around a table dividing expenses, impressionistic rendering of hands and paper money, soft afternoon light, outdoor terrace setting with umbrellas",
            "filename": "split_expenses",
            "caption": "Split Expenses - Fair Division"
        },
        {
            "prompt": style_prefix + "group of conventionally attractive friends posing together after a meal, empty wine glasses and plates on table, golden hour lighting, painterly brushwork capturing joy and camaraderie",
            "filename": "group_photo",
            "caption": "Group Photo - Celebration"
        }
    ]
    
    media_dir = Path("media/sample_images")
    media_dir.mkdir(parents=True, exist_ok=True)
    
    prompts_file = media_dir / "prompts.txt"
    
    with open(prompts_file, "w") as f:
        f.write(f"Generated on: {datetime.now()}\n\n")
        
        for i, image_data in enumerate(image_prompts, 1):
            print(f"\nGenerating {image_data['caption']} (3 alternatives)")
            
            # Generate 3 alternatives for each image
            for alt in range(1, 4):
                print(f"  Alternative {alt}/3...")
                
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
                        # Save with alternative number in filename
                        filename = f"{image_data['filename']}_alt{alt}.png"
                        image_path = media_dir / filename
                        with open(image_path, "wb") as img_file:
                            img_file.write(img_response.content)
                        
                        print(f"    ✓ Saved to {image_path}")
                        
                        f.write(f"Image {i}-{alt}: {filename}\n")
                        f.write(f"Caption: {image_data['caption']}\n")
                        f.write(f"Alternative: {alt}\n")
                        f.write(f"Prompt: {image_data['prompt']}\n")
                        f.write(f"URL: {image_url}\n\n")
                    else:
                        print(f"    ✗ Failed to download image")
                        
                except Exception as e:
                    print(f"    ✗ Error generating image: {e}")
    
    print(f"\nPrompts saved to: {prompts_file}")
    print("All images generated successfully!")


if __name__ == "__main__":
    generate_and_save_images()