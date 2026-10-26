import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

class LabelEditor:
    
    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        """
        UPS Label ke liye direct coordinate-based address replace (No OCR needed)
        """
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor")
            return None
        
        h, w = img.shape[:2]
        
        # UPS Label ke fix coordinates (SHIP TO: box ke liye)
        x1, y1 = int(w * 0.15), int(h * 0.18)
        x2, y2 = int(w * 0.60), int(h * 0.38)
        
        # Purane address ko white se dhak dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font load karein (Windows ka Arial font)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
        except:
            font = ImageFont.load_default()
            
        name = new_address_data.get('name', '3PL Warehouse')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein
        draw.text((x1 + 10, y1 + 10), address_text, fill="black", font=font)
        
        # Save karein
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img)
        
        print(f"✅ Address replaced successfully!")
        return output_path