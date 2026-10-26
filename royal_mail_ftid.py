import os
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
        """Check if warehouse is allowed"""
        if not warehouse_name:
            return False
        for allowed in RoyalMailFTID.ALLOWED_WAREHOUSES:
            if allowed.lower() in warehouse_name.lower():
                return True
        return False
    
    @staticmethod
    def alter_tracking_number(tracking_text):
        """Alter 1 digit of the tracking number (Fallback utility)"""
        if not tracking_text or len(tracking_text) < 2:
            return tracking_text
        
        chars = list(tracking_text)
        last_char = chars[-1]
        
        if last_char.isdigit():
            new_digit = str((int(last_char) + 1) % 10)
            chars[-1] = new_digit
        else:
            chars[-1] = chr(ord(last_char) + 1) if last_char != 'Z' else 'A'
        
        return ''.join(chars)
    
    @staticmethod
    def process_label(image_path, warehouse_name, warehouse_address, warehouse_postcode, output_path):
        """
        Complete Royal Mail FTID processing pipeline.
        Uses RoyalMailProcessor to handle OCR, address replacement, and DataMatrix regeneration.
        """
        print("=" * 50)
        print("📦 Royal Mail FTID Processing")
        print("=" * 50)
        
        # 1. Validate warehouse
        if not RoyalMailFTID.validate_warehouse(warehouse_name):
            print(f"⚠️ Warehouse {warehouse_name} not in allowed list. Proceeding with general logic.")
        
        # 2. Prepare warehouse data dict
        warehouse_data = {
            "name": warehouse_name,
            "address": warehouse_address,
            "postcode": warehouse_postcode
        }
        
        # 3. Call the actual processing logic from royal_mail_processor.py
        try:
            from royal_mail_processor import RoyalMailProcessor
            
            result = RoyalMailProcessor.process_royal_mail_label(
                input_path=image_path,
                warehouse=warehouse_data,
                output_path=output_path
            )
            
            if result and os.path.exists(output_path):
                print("\n" + "=" * 50)
                print("✅ Royal Mail FTID Complete!")
                print("=" * 50)
                return output_path
            else:
                print("❌ Processor failed to generate output.")
                return None
                
        except Exception as e:
            print(f"❌ Error in RoyalMailFTID processing: {e}")
            import traceback
            traceback.print_exc()
            return None