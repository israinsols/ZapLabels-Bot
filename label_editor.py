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
        
        # FIX: OCR ko hata kar direct safe coordinates use kar rahe hain
        # Yeh area sirf address ke liye reserve hai (barcode se upar)
        x1 = int(w * 0.15) # Left se thoda aage
        y1 = int(h * 0.10) # Top se thoda neeche
        
        # Box ki width aur height
        x2 = int(w * 0.65)
        y2 = int(h * 0.28) # Neeche wale barcode se upar tak
        
        # Purane address ko pura white kar dein
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Naya Address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font size
        font_size = max(16, int(w * 0.018)) 
        
        font = None
        try:
            # Arial Bold (Original jaisa)
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
        
        # Text draw karein (y1 + 10 se shuru karein taake saaf lage)
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=5)
        
        # Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced cleanly without any leftover text.")
        return output_path