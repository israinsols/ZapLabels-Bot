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
        
        # FIX: Left se 0.08 (taake border ke andar rahe) aur top se 0.02
        x1 = int(w * 0.08) 
        y1 = int(h * 0.02) 
        
        # Width aur Height fix ki hai taake barcode safe rahe aur '1 OF 1' bhi chhup jaye
        x2 = int(w * 0.92) # Right side tak
        y2 = int(h * 0.32) # Barcode se pehle tak
        
        # Purane pura top area ko white kar dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # FIX: Original label jaisa font (Monospace ya Courier)
        font_size = max(14, int(w * 0.018)) 
        
        font = None
        try:
            # Courier New Bold (jo thermal printers UPS ke liye use karte hain)
            font = ImageFont.truetype("courbd.ttf", font_size)
        except:
            try:
                # Agar courier na mile toh fallback Arial Bold
                font = ImageFont.truetype("arialbd.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Naya Address Format
        address_text = f"SHIP TO:\nTO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein (Exact padding ke sath)
        draw.multiline_text((x1 + 20, y1 + 20), address_text, fill="black", font=font, spacing=5)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Perfect: Box inside borders, font matched.")
        return output_path