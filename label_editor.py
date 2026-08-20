import cv2
import numpy as np
from PIL import Image
import pytesseract
import re
import os

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class LabelEditor:
    
    @staticmethod
    def detect_address_region(image_path):
        """
        Detect address region on label using OCR
        """
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Use OCR to find address text
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(gray, config=custom_config)
        
        print(f"📝 OCR Text: {text[:200]}...")
        
        # Find postcode pattern
        postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        postcodes = re.findall(postcode_pattern, text)
        
        # Find building name/address lines
        lines = text.split('\n')
        address_lines = []
        
        for line in lines:
            line = line.strip()
            if len(line) > 5 and not line.isdigit():
                address_lines.append(line)
        
        if postcodes:
            print(f"✅ Found postcode: {postcodes[0]}")
            return {
                'postcode': postcodes[0],
                'address_lines': address_lines[:5],
                'full_text': text
            }
        return None
    
    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        """
        Replace address on label with new 3PL address
        """
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        # Evri specific basic wipe (hardcoded box based on typical Evri label layout)
        # The address is usually on the left side, roughly middle.
        # Let's white out a large rectangle on the left side
        h, w = img.shape[:2]
        
        # Approximate region for Evri address box (Destination)
        # Cleanly inside the destination inner border:
        x1, y1 = int(w * 0.075), int(h * 0.490)
        x2, y2 = int(w * 0.505), int(h * 0.672)
        
        # Draw white rectangle
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        # Convert to PIL for text overlay
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img_pil)
        
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
            
        # Write new address
        street = new_address_data.get('street', new_address_data.get('address', '').split(',')[0].strip())
        city = new_address_data.get('city', new_address_data.get('address', '').split(',')[1].strip() if ',' in new_address_data.get('address', '') else 'London')
        
        address_text = f"{new_address_data['name']}\n{street}\n{city}\n{new_address_data['postcode']}"
        draw.text((x1 + 10, y1 + 10), address_text, fill="black", font=font)
        
        # Convert back and save
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        cv2.imwrite(output_path, img)
        print(f"✅ Label saved with new address")
        return output_path
    
    @staticmethod
    def create_ftid_label(original_path, warehouse, carrier, output_path):
        """
        Complete FTID label creation pipeline
        """
        print("=" * 50)
        print("📦 Creating FTID Label")
        print("=" * 50)
        
        # Step 1: Detect old address
        print("\n📌 Step 1: Detecting old address...")
        old_address = LabelEditor.detect_address_region(original_path)
        
        if old_address:
            print(f"   Old Postcode: {old_address['postcode']}")
        
        # Step 2: Format new address
        print("\n📌 Step 2: Formatting new 3PL address...")
        new_address = {
            'name': warehouse['name'],
            'street': warehouse['address'].split(',')[0].strip(),
            'city': warehouse['address'].split(',')[1].strip() if ',' in warehouse['address'] else 'London',
            'postcode': warehouse['postcode']
        }
        print(f"   New Address: {new_address}")
        
        # Step 3: Replace address on label
        print("\n📌 Step 3: Replacing address...")
        result = LabelEditor.replace_address_on_label(original_path, new_address, output_path)
        
        print("\n" + "=" * 50)
        print("✅ FTID Label Created Successfully!")
        print("=" * 50)
        
        return result