import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

class LabelEditor:
    
    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        """
        UPS Label ke liye direct coordinate-based address replace.
        """
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor")
            return None
        
        h, w = img.shape[:2]
        
        # UPS Label ka "SHIP TO:" wala area (Barcode aur neeche wali cheezon se upar)
        # X: Left se 15% (SHIP TO ke baad), Y: Top se 18% (SHIP TO ke neeche)
        x1, y1 = int(w * 0.18), int(h * 0.15)
        x2, y2 = int(w * 0.60), int(h * 0.35)
        
        # Purane address ko white se dhak dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font load karein (Windows ya Linux ke liye fallback)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '3PL Warehouse')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Format address properly
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein
        draw.text((x1 + 10, y1 + 10), address_text, fill="black", font=font)
        
        # Save karein (High quality)
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced successfully at ({x1}, {y1}) to ({x2}, {y2})")
        return output_path