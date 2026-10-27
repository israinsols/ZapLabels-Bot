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
        
        # FIX: Box ko bada kiya hai taake pura purana address chhup jaye
        x1 = int(w * 0.15) 
        y1 = int(h * 0.10) 
        
        x2 = int(w * 0.75) # Width barha di
        y2 = int(h * 0.32) # Height barha di taake purana text pura dhak jaye
        
        # Purane address ko white kar dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # FIX: Font size chota kiya hai taake naya address box ke andar fit ho jaye
        font_size = max(12, int(w * 0.015)) 
        
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
        
        # Naya address format
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=5)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced cleanly. Box size increased.")
        return output_path