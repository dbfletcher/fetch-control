import os
from PIL import Image

HIGHRES_DIR = "/var/www/fetch/media/highres"
LOWRES_DIR = "/var/www/fetch/media/lowres"
THUMB_SIZE = (400, 400)

def generate_thumbnails():
    # Ensure lowres directory exists
    os.makedirs(LOWRES_DIR, exist_ok=True)
    
    for filename in os.listdir(HIGHRES_DIR):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            highres_path = os.path.join(HIGHRES_DIR, filename)
            lowres_path = os.path.join(LOWRES_DIR, filename)
            
            # Only process if thumbnail doesn't exist
            if not os.path.exists(lowres_path):
                print(f"Processing: {filename}...")
                with Image.open(highres_path) as img:
                    img.thumbnail(THUMB_SIZE)
                    img.save(lowres_path, optimize=True, quality=85)
                print(f"✅ Thumbnail created for {filename}")

if __name__ == "__main__":
    generate_thumbnails()
