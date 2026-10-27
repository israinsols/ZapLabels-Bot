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
        
        # 1. Find the exact location of "SHIP TO" using OCR
        data = pytesseract.image_to_data(gray, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        
        address_x, address_y = None, None
        for i, text in enumerate(data['text']):
            if "SHIP" in text.upper() or "TO:" in text.upper():
                address_x = data['left'][i]
                address_y = data['top'][i]
                break
        
        # Fallback agar SHIP TO na mile (Top Left area)
        if address_x is None:
            address_x = int(w * 0.05)
            address_y = int(h * 0.15)

        # 2. Set the box slightly below and to the right of "SHIP TO"
        # But make sure it doesn't go too far down (saving the barcode)
        x1 = address_x + int(w * 0.05) # 5% right of SHIP TO
        y1 = address_y + int(h * 0.02) # 2% below SHIP TO
        
        # Width and Height of the white box
        x2 = x1 + int(w * 0.35) 
        y2 = y1 + int(h * 0.10) # Only cover 10% height (Address area only)
        
        # Safe check: ensure we don't overflow image
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        # White out only the address text area
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # 3. Write New Address
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
        except:
            font = ImageFont.load_default()
            
        name = new_address_data.get('name', '3PL Warehouse')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Draw text inside the safe box
        draw.text((x1 + 5, y1 + 5), address_text, fill="black", font=font)
        
        # 4. Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced carefully at ({x1}, {y1}) to ({x2}, {y2})")
        return output_path