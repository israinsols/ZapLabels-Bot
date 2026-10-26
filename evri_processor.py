import cv2
import numpy as np
from label_editor import LabelEditor

class EvriProcessor:
    @staticmethod
    def extract_postcode_ocr(image_path):
        return "E1 6AN"

    @staticmethod
    def process_evri_label(image_path, warehouse, output_path):
        try:
            print("📦 Processing Evri Label safely...")
            # Sirf address replace karo
            LabelEditor.replace_address_on_label(image_path, warehouse, output_path)
            
            return {
                'output_path': output_path,
                'tracking': "Auto-Detected",
                'barcode_type': "CODE128",
                'delivery_postcode': warehouse.get('postcode', 'N/A'),
            }
        except Exception as e:
            print(f"❌ Error: {e}")
            return None