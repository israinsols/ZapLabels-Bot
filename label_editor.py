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
        
        # 1. OCR se "SHIP TO" ka exact box dhoondein
        try:
            data = pytesseract.image_to_data(gray, config='--oem 3 --psm 6', output_type=pytesseract.Output.DICT)
        except Exception as e:
            print(f"OCR Error: {e}")
            data = {'text': [], 'left': [], 'top': []}

        ship_x, ship_y = None, None
        for i, text in enumerate(data['text']):
            if "SHIP" in text.upper() or "TO:" in text.upper():
                ship_x = data['left'][i]
                ship_y = data['top'][i]
                break
        
        # 2. Safe Box coordinates
        if ship_x is not None:
            x1 = ship_x - 10
            y1 = ship_y - 10
            x2 = x1 + int(w * 0.55) # 55% width
            y2 = y1 + int(h * 0.18) # 18% height
        else:
            # Fallback (agar OCR fail ho)
            x1, y1 = int(w * 0.05), int(h * 0.05)
            x2, y2 = int(w * 0.60), int(h * 0.25)

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        # 3. White out
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # 4. Draw Text (Using 100% safe fonts)
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        font_size = max(14, int(w * 0.016))
        
        font = None
        # Windows fonts (Arial)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except:
            # Linux/Railway font
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            except:
                font = ImageFont.load_default()
            
        name = new_address_data.get('name', '')
        street = new_address_data.get('street', '')
        city = new_address_data.get('city', 'London')
        postcode = new_address_data.get('postcode', 'E1 6AN')
        
        # Text to write
        address_text = f"TO NAME\n{name}\n{street}\n{city}\n{postcode}"
        
        # Draw text
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=4)
        
        # 5. Save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        
        print(f"✅ Address replaced with OCR logic.")
        return output_path