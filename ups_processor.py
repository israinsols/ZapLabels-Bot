import cv2
import numpy as np
import fitz  # PyMuPDF
import os
from label_editor import LabelEditor

class UPSProcessor:
    @staticmethod
    def extract_postcode_ocr(image_path):
        return "E1 6AN"

    @staticmethod
    def process_ups_label(image_path, warehouse, output_path):
        try:
            print("📦 Processing UPS Label (Manual PDF Mode)...")
            
            # 1. PDF ko Image mein convert karein
            if image_path.lower().endswith('.pdf'):
                doc = fitz.open(image_path)
                page = doc[0]
                mat = fitz.Matrix(3.0, 3.0) # High resolution
                pix = page.get_pixmap(matrix=mat)
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                
                if pix.n == 4:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                else:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    
                temp_img_path = output_path + "_temp.jpg"
                cv2.imwrite(temp_img_path, img_array)
                doc.close()
                source_path = temp_img_path
            else:
                source_path = image_path

            # 2. Address Replace
            result = LabelEditor.replace_address_on_label(source_path, warehouse, output_path)
            
            # 3. Temp file cleanup
            if image_path.lower().endswith('.pdf') and os.path.exists(source_path):
                os.remove(source_path)

            if result and os.path.exists(output_path):
                return {'output_path': output_path, 'tracking': 'N/A', 'barcode_type': 'N/A', 'delivery_postcode': 'N/A'}
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error in UPS Processor: {e}")
            return None