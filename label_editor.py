import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import os

class LabelEditor:
    
    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor")
            return None
        
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Find "SHIP TO:" using OCR
        data = pytesseract.image_to_data(gray, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        
        ship_x, ship_y = None, None
        for i, text in enumerate(data['text']):
            text_upper = text.upper()
            if "SHIP" in text_upper or text_upper == "TO:":
                ship_x = data['left'][i]
                ship_y = data['top'][i]
                break
        
        # 2. Set the box (Barcode se upar tak)
        if ship_x is not None:
            x1 = ship_x + int(w * 0.06) 
            y1 = ship_y + int(h * 0.01) 
            x2 = x1 + int(w * 0.45) 
            y2 = y1 + int(h * 0.20) # Box ko bada kar diya taake text pura aaye
        else:
            x1, y1 = int(w * 0.15), int(h * 0.10)
            x2, y2 = int(w * 0.65), int(h * 0.30)

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        # White out purana area
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # 3. Draw New Address
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Font size thoda bada kiya hai
        font_size = max(16, int(w * 0.018)) 
        
        font = None
        try:
            # Arial Bold (Har system par chalta hai)
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
        
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein
        draw.multiline_text((x1 + 5, y1 + 5), address_text, fill="black", font=font, spacing=4)
        
        # 4. Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced with Arial Bold font!")
        return output_path