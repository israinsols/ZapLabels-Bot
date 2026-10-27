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
        
        # FIX: OCR hata diya hai. Ab direct pura top area white hoga.
        # Label ki border ke andar rehne ke liye x1 aur y1 ko thoda adjust kiya hai.
        x1 = int(w * 0.05)  # Left border se andar
        y1 = int(h * 0.03)  # Top border se andar
        
        x2 = int(w * 0.95)  # Right border tak
        y2 = int(h * 0.30)  # Barcode (TX 786) se pehle tak
        
        # Pura top area white kar dein (Sender + Receiver)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font size
        font_size = max(14, int(w * 0.018)) 
        
        font = None
        # Font loading (Safe for Windows & Linux/Railway)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Address format
        address_text = f"SHIP TO:\nTO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein (Thoda neeche se taake top border saaf rahe)
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=5)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Final Fix: Whole top area cleared.")
        return output_path