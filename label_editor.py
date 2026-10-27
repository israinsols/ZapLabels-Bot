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
        
        # FIX: Fixed coordinates taake black border kabhi na kate
        x1 = int(w * 0.08)  # Border se andar
        y1 = int(h * 0.02)  # Top se andar
        x2 = int(w * 0.95)  # Right side tak
        y2 = int(h * 0.28)  # Barcode se bilkul pehle tak
        
        # White box (pura area clear)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font size (chota kiya hai taake box ke andar fit ho jaye)
        font_size = max(12, int(w * 0.014)) 
        
        font = None
        try:
            # Arial font (har jagah chalta hai)
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Address format (SHIP TO ke sath)
        address_text = f"SHIP TO:\nTO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein (x1, y1 se thoda aage)
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=5)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced with fixed box and smaller font.")
        return output_path