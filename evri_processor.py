import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image
import re
import pytesseract
import barcode as barcode_lib
from barcode.writer import ImageWriter
import io

import shutil

# Set Tesseract path
if shutil.which("tesseract"):
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class EvriProcessor:
    
    @staticmethod
    def detect_barcode(image_path):
        """
        Evri label se barcode detect karo — multiple strategies
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("❌ Image not found or invalid")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        strategies = [
            ("2x upscale",        cv2.resize(gray, (w*2, h*2), interpolation=cv2.INTER_CUBIC), 2.0, 0),
            ("3x upscale",        cv2.resize(gray, (w*3, h*3), interpolation=cv2.INTER_CUBIC), 3.0, 0),
            ("raw gray",          gray, 1.0, 0),
            ("Otsu",              cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1], 1.0, 0),
            ("adaptive",          cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2), 1.0, 0),
            ("CLAHE",             cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray), 1.0, 0),
            ("sharpened",         cv2.filter2D(gray, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])), 1.0, 0),
            ("bottom half",       gray[h//2:, :], 1.0, h//2),
            ("top half",          gray[:h//2, :], 1.0, 0),
        ]
        
        decoded = None
        successful_scale = 1.0
        successful_offset_y = 0
        
        for name, processed, scale, off_y in strategies:
            print(f"   🔍 Trying strategy: {name}...")
            current_decoded = pyzbar_decode(Image.fromarray(processed))
            
            # Prefer strategy that finds CODE128
            code128_found = any(d.type == 'CODE128' for d in current_decoded)
            if code128_found or (current_decoded and not decoded):
                decoded = current_decoded
                successful_scale = scale
                successful_offset_y = off_y
                if code128_found:
                    print(f"   ✅ Found CODE128 barcode with strategy: {name}")
                    break
        
        if not decoded:
            raise ValueError("❌ No barcode found in image after all strategies")
        
        barcodes = []
        for code in decoded:
            try:
                data = code.data.decode('utf-8')
            except UnicodeDecodeError:
                data = code.data.decode('latin-1')
                
            bx = int(code.rect.left / successful_scale)
            by = int(code.rect.top / successful_scale) + successful_offset_y
            bw = int(code.rect.width / successful_scale)
            bh = int(code.rect.height / successful_scale)
            
            # If pyzbar returned 0 dimensions, fallback to typical bottom barcode zone
            if bw <= 10 or bh <= 10:
                bw = int(w * 0.70)
                bh = int(h * 0.17)
                bx = int((w - bw) / 2)
                by = int(h * 0.78)
            
            barcodes.append({
                'type': code.type,
                'data': data,
                'position': (bx, by, bw, bh)
            })
            print(f"✅ Barcode detected: {code.type} → {data} at {barcodes[-1]['position']}")
        
        return barcodes, img
    
    @staticmethod
    def extract_tracking(barcode_data):
        """
        Evri tracking number extract karo
        """
        for pattern in [r'H\d{15}', r'P\d{15}', r'[A-Z][A-Z0-9]{15}', r'[A-Z0-9]{16}']:
            match = re.search(pattern, barcode_data)
            if match:
                tracking = match.group()
                print(f"📦 Tracking number: {tracking}")
                return tracking
        
        # Fallback to alphanumeric cleaning
        cleaned = re.sub(r'[^A-Z0-9]', '', barcode_data.upper())
        if len(cleaned) >= 16:
            return cleaned[:16]
            
        print("⚠️ No standard Evri tracking pattern found, using cleaned data")
        return cleaned or barcode_data
    
    @staticmethod
    def extract_postcode_ocr(image_path):
        """
        OCR se postcode extract karo
        """
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        try:
            text = pytesseract.image_to_string(gray, config='--oem 3 --psm 6')
            postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
            match = re.search(postcode_pattern, text.upper())
            if match:
                print(f"📮 Postcode: {match.group()}")
                return match.group()
        except Exception as e:
            print(f"⚠️ Postcode OCR exception: {e}")
        
        print("⚠️ No postcode found via OCR")
        return None
    
    @staticmethod
    def regenerate_barcode(data, barcode_type='CODE128', size=None):
        """
        Evri barcode regenerate karo (Code128)
        """
        try:
            # Clean data for Code128 standard
            clean_data = re.sub(r'[^A-Za-z0-9]', '', data)
            my_barcode = barcode_lib.get('code128', clean_data, writer=ImageWriter())
            rv = io.BytesIO()
            my_barcode.write(rv)
            rv.seek(0)
            img = Image.open(rv).convert('RGB')
            img_array = np.array(img)
            
            if size and size[0] > 10 and size[1] > 10:
                img_array = cv2.resize(img_array, size, interpolation=cv2.INTER_AREA)
            
            print(f"✅ Barcode regenerated ({barcode_type}) for {clean_data}")
            return img_array
            
        except Exception as e:
            print(f"❌ Error regenerating barcode: {e}")
            return None
    
    @staticmethod
    def composite_barcode(original_img_path, new_barcode, position, output_path):
        """
        Regenerated barcode ko label pe composite karo
        """
        try:
            img = cv2.imread(original_img_path)
            if img is None:
                raise ValueError("❌ Could not read original image")
            
            img_h, img_w = img.shape[:2]
            x, y, w, h = position
            
            # Bounds checking & sane defaults
            if w <= 10 or h <= 10:
                w = int(img_w * 0.70)
                h = int(img_h * 0.17)
                x = int((img_w - w) / 2)
                y = int(img_h * 0.78)
            
            # White out the old barcode area plus margin below for old text
            y_start = max(0, y)
            y_end = min(img_h, y + h + int(img_h * 0.05))
            x_start = max(0, x - 5)
            x_end = min(img_w, x + w + 5)
            
            img[y_start:y_end, x_start:x_end] = 255
            
            # Resize barcode to target dimensions
            target_w = x_end - x_start
            target_h = y_end - y_start
            
            resized_bc = cv2.resize(new_barcode, (target_w, target_h), interpolation=cv2.INTER_AREA)
            if len(resized_bc.shape) == 3:
                resized_bc_bgr = cv2.cvtColor(resized_bc, cv2.COLOR_RGB2BGR)
            else:
                resized_bc_bgr = cv2.cvtColor(resized_bc, cv2.COLOR_GRAY2BGR)
                
            img[y_start:y_end, x_start:x_end] = resized_bc_bgr
            
            cv2.imwrite(output_path, img)
            print(f"✅ Barcode composited successfully! Output: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error compositing barcode: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def process_evri_label(image_path, warehouse, output_path):
        """
        Complete Evri label processing pipeline
        """
        print("=" * 50)
        print("📦 Evri Label Processing")
        print("=" * 50)
        
        try:
            # Step 1: Detect barcode
            print("\n📌 Step 1: Detecting barcode...")
            barcodes, img = EvriProcessor.detect_barcode(image_path)
            
            # Step 2: Extract tracking
            print("\n📌 Step 2: Extracting tracking number...")
            # Prefer CODE128 barcode data
            selected_barcode = next((b for b in barcodes if b['type'] == 'CODE128'), barcodes[0])
            tracking = EvriProcessor.extract_tracking(selected_barcode['data'])
            
            # Step 3: Extract postcode
            print("\n📌 Step 3: Extracting delivery postcode...")
            postcode = EvriProcessor.extract_postcode_ocr(image_path)
            
            # Step 4: Replace address
            print("\n📌 Step 4: Replacing delivery address...")
            from label_editor import LabelEditor
            LabelEditor.replace_address_on_label(image_path, warehouse, output_path)
            
            # Step 5 & 6: Regenerate and Composite barcode
            print("\n📌 Step 5 & 6: Regenerating and Compositing barcode...")
            new_barcode = EvriProcessor.regenerate_barcode(
                selected_barcode['data'],
                'CODE128',
                (selected_barcode['position'][2], selected_barcode['position'][3])
            )
            
            if new_barcode is not None:
                EvriProcessor.composite_barcode(
                    output_path, new_barcode,
                    selected_barcode['position'], output_path
                )
            else:
                print("⚠️ Could not regenerate barcode image.")
            
            print("\n" + "=" * 50)
            print("✅ Evri Label Processing Complete!")
            print(f"📁 Output: {output_path}")
            print("=" * 50)
            
            return {
                'output_path': output_path,
                'tracking': tracking,
                'barcode_type': selected_barcode['type'],
                'delivery_postcode': postcode,
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return None
