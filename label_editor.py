import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

class LabelEditor:
    
    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor")
            return None
        
        h, w = img.shape[:2]
        
        # FIX: Label ka top-left corner 100% white karein (Sender + Receiver ke liye)
        # Top se 1% se shuru, Left se 1% se shuru
        x1 = int(w * 0.01) 
        y1 = int(h * 0.01) 
        
        # Width aur Height fix ki hai taake barcode bilkul safe rahe
        # Right side tak 60% (taake text saaf ho) aur Neeche 32% tak (barcode 35% par shuru hota hai)
        x2 = int(w * 0.65) 
        y2 = int(h * 0.32) 
        
        # Purane pura top area ko white kar dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font size (Arial Bold)
        font_size = max(14, int(w * 0.016)) 
        
        font = None
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Naya Address Format (TO NAME ke sath)
        address_text = f"SHIP TO:\nTO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein (Top left se thoda gap de kar)
        draw.multiline_text((x1 + 15, y1 + 15), address_text, fill="black", font=font, spacing=4)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Perfect: Top area cleared and address applied.")
        return output_path