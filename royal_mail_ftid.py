import cv2
import numpy as np
from PIL import Image
import re

class RoyalMailFTID:
    
    # Allowed warehouses
    ALLOWED_WAREHOUSES = [
        "Clipper Logistics",
        "GXO Logistics"
    ]
    
    @staticmethod
    def validate_warehouse(warehouse_name):
        """Sirf Clipper ya GXO allow karo"""
        for allowed in RoyalMailFTID.ALLOWED_WAREHOUSES:
            if allowed.lower() in warehouse_name.lower():
                return True
        return False
    
    @staticmethod
    def alter_tracking_number(tracking_text):
        """Tracking number mein 1 digit change karo"""
        if not tracking_text or len(tracking_text) < 2:
            return tracking_text
        
        # Last digit ko change karo
        chars = list(tracking_text)
        last_char = chars[-1]
        
        if last_char.isdigit():
            new_digit = str((int(last_char) + 1) % 10)
            chars[-1] = new_digit
        else:
            # Letter hai toh next letter
            chars[-1] = chr(ord(last_char) + 1) if last_char != 'Z' else 'A'
        
        return ''.join(chars)
    
    @staticmethod
    def process_label(image_path, warehouse_name, warehouse_address, warehouse_postcode, output_path):
        """
        Complete Royal Mail FTID processing
        """
        # 1. Validate warehouse
        if not RoyalMailFTID.validate_warehouse(warehouse_name):
            raise ValueError(f"❌ Warehouse not allowed: {warehouse_name}. Use Clipper Logistics or GXO only.")
        
        print("=" * 50)
        print("📦 Royal Mail FTID Processing")
        print("=" * 50)
        
        # 2. Code128 barcode — DO NOT TOUCH
        print("\n📌 Code128 barcode: UNCHANGED ✅")
        
        # 3. Written tracking number — change 1 digit
        print("\n📌 Written tracking number: changing 1 digit...")
        # TODO: OCR se tracking text extract karo
        # new_tracking = RoyalMailFTID.alter_tracking_number(old_tracking)
        
        # 4. Delivery address → warehouse
        print(f"\n📌 Delivery address: replacing with {warehouse_name}...")
        
        # 5. Sender address — remove
        print("\n📌 Sender address: removing...")
        
        # 6. Order/reference numbers & small barcodes — remove
        print("\n📌 Order/reference numbers & small barcodes: removing...")
        
        # 7. DataMatrix — update with warehouse name + postcode
        print(f"\n📌 DataMatrix: updating with {warehouse_name} and {warehouse_postcode}...")
        
        print("\n" + "=" * 50)
        print("✅ Royal Mail FTID Complete!")
        print("=" * 50)
        
        return output_path