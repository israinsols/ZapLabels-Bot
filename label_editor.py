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
        
        # 1. OCR se exact "SHIP TO:" ka box dhoondein
        data = pytesseract.image_to_data(gray, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        
        ship_x, ship_y = None, None
        for i, text in enumerate(data['text']):
            text_upper = text.upper()
            # Sirf "SHIP TO" par focus karein, "FROM" ya "ADDRESS" par nahi
            if "SHIP" in text_upper or text_upper == "TO:":
                ship_x = data['left'][i]
                ship_y = data['top'][i]
                break
        
        # 2. Box set karein
        if ship_x is not None:
            # SHIP TO ke thoda right aur neeche (Safe area)
            x1 = ship_x + int(w * 0.06) 
            y1 = ship_y + int(h * 0.02) 
            # Box ki width aur height (Barcode se upar)
            x2 = x1 + int(w * 0.40) 
            y2 = y1 + int(h * 0.16) 
        else:
            # Fallback: Agar OCR fail ho jaye, toh fixed safe area (Top Left)
            x1, y1 = int(w * 0.15), int(h * 0.12)
            x2, y2 = int(w * 0.60), int(h * 0.28)

        # Image bounds ke andar rakhein
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        # 3. White out sirf address area
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # 4. Naya address likhein
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # Dynamic font size (taake text box ke andar fit ho jaye)
        font_size = max(14, int(w * 0.018)) 
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '3PL Warehouse')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Text draw karein
        draw.text((x1 + 5, y1 + 5), address_text, fill="black", font=font)
        
        # 5. Save karein
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced safely at ({x1}, {y1})")
        return output_path