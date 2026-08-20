import cv2
import numpy as np
from pylibdmtx.pylibdmtx import decode, encode
from PIL import Image
import io
import re

class DataMatrixProcessor:
    
    @staticmethod
    def detect_datamatrix(image_path):
        """
        Step 1: Label se Data Matrix detect karo
        """
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("❌ Image not found or invalid")
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # ===== ENHANCE IMAGE FOR BETTER DETECTION =====
        # Method 1: Try original
        decoded = decode(Image.fromarray(gray))
        
        # Method 2: Try resized
        if not decoded:
            scale = 2
            width = int(gray.shape[1] * scale)
            height = int(gray.shape[0] * scale)
            resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_CUBIC)
            decoded = decode(Image.fromarray(resized))
        
        # Method 3: Try threshold
        if not decoded:
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            decoded = decode(Image.fromarray(thresh))
        
        # Method 4: Try adaptive threshold
        if not decoded:
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            decoded = decode(Image.fromarray(thresh))
        
        if not decoded:
            raise ValueError("❌ No Data Matrix found in image")
        
        # Get position
        rect = decoded[0].rect
        x, y, w, h = rect.left, rect.top, rect.width, rect.height
        
        print(f"✅ Data Matrix detected at position: ({x}, {y}) size: {w}x{h}")
        
        return decoded[0], (x, y, w, h), img
    
    @staticmethod
    def decode_payload(decoded_data):
        """
        Step 2: Decode payload
        """
        payload = decoded_data.data.decode('utf-8')
        print(f"📦 Raw payload: {payload}")
        return payload
    
    @staticmethod
    def extract_fields(payload):
        """
        Step 3: Extract fields - Postcode, building name, tracking, service type
        """
        fields = {
            'service_type': '',
            'tracking': '',
            'postcode': '',
            'building_name': '',
            'delivery_point': ''
        }
        
        try:
            # Try to extract postcode using regex (UK format)
            postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
            postcode_match = re.search(postcode_pattern, payload)
            if postcode_match:
                fields['postcode'] = postcode_match.group()
            
            # Try to extract tracking (9 digits)
            tracking_match = re.search(r'\d{9}', payload)
            if tracking_match:
                fields['tracking'] = tracking_match.group()
            
            # Try to extract service type (first 2 chars)
            if len(payload) >= 2:
                fields['service_type'] = payload[0:2]
            
            # Building name - try to extract
            if postcode_match:
                # Get text after postcode
                after_postcode = payload[postcode_match.end():].strip()
                # Try to find building name (usually before postcode)
                before_postcode = payload[:postcode_match.start()].strip()
                if before_postcode:
                    # Get last word as building name
                    parts = before_postcode.split()
                    if parts:
                        fields['building_name'] = parts[-1] if len(parts) > 1 else before_postcode
            
            print(f"📋 Extracted fields:")
            print(f"   Service Type: {fields['service_type']}")
            print(f"   Tracking: {fields['tracking']}")
            print(f"   Postcode: {fields['postcode']}")
            print(f"   Building Name: {fields['building_name']}")
            print(f"   Delivery Point: {fields['delivery_point']}")
            
        except Exception as e:
            print(f"❌ Error extracting fields: {e}")
        
        return fields
    
    @staticmethod
    def parse_rm_structure(payload):
        """
        Step 4: Parse Royal Mail specific structure
        """
        structure = {
            'raw': payload,
            'length': len(payload),
            'format': 'Unknown'
        }
        
        if len(payload) == 40:
            structure['format'] = 'Standard RM (40 chars)'
        elif len(payload) == 30:
            structure['format'] = 'Short RM (30 chars)'
        else:
            structure['format'] = f'Custom ({len(payload)} chars)'
        
        print(f"📊 Structure: {structure['format']}")
        return structure
    
    @staticmethod
    def generate_datamatrix(payload, size=(100, 100)):
        """
        Generate new Data Matrix with updated payload
        """
        try:
            # Encode payload
            encoded = encode(payload.encode('utf-8'))
            
            # Convert to numpy array
            if isinstance(encoded, Image.Image):
                img_array = np.array(encoded, dtype=np.uint8)
            else:
                # pylibdmtx encode returns an object with pixels, width, height
                try:
                    if hasattr(encoded, 'pixels') and hasattr(encoded, 'width'):
                        img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
                        # Convert to grayscale then binary
                        img = img.convert('L')
                        img_array = np.array(img, dtype=np.uint8)
                    else:
                        img_array = np.array(encoded, dtype=np.uint8)
                        if img_array.max() > 255:
                            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
                except Exception as inner_e:
                    print(f"Fallback generation error: {inner_e}")
                    img_array = np.array(encoded.pixels) if hasattr(encoded, 'pixels') else np.array(encoded)
            
            # Ensure binary (0 and 255)
            img_array = np.where(img_array > 127, 255, 0).astype(np.uint8)
            
            # Resize using OpenCV
            if size:
                img_array = cv2.resize(img_array, size, interpolation=cv2.INTER_NEAREST)
                # After resize, ensure binary again
                img_array = np.where(img_array > 127, 255, 0).astype(np.uint8)
            
            print(f"✅ Data Matrix generated! Shape: {img_array.shape}")
            return img_array
        except Exception as e:
            print(f"❌ Error generating Data Matrix: {e}")
            return None
    
    @staticmethod
    def update_payload(old_payload, new_postcode, new_building_name):
        """
        Update payload with new address data
        """
        new_payload = old_payload
        
        # Replace postcode
        postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        postcode_match = re.search(postcode_pattern, old_payload)
        
        if postcode_match:
            old_postcode = postcode_match.group()
            # Replace all occurrences
            new_payload = new_payload.replace(old_postcode, new_postcode)
            print(f"✅ Postcode replaced: {old_postcode} → {new_postcode}")
        
        # Replace building name (try to find and replace)
        # Look for the building name before postcode
        if postcode_match:
            before_postcode = old_payload[:postcode_match.start()].strip()
            # Find a word that looks like a building name (capitalized, length > 2)
            words = before_postcode.split()
            for word in reversed(words):
                if len(word) > 2 and word[0].isupper():
                    old_building = word
                    new_payload = new_payload.replace(old_building, new_building_name)
                    print(f"✅ Building name replaced: {old_building} → {new_building_name}")
                    break
        
        return new_payload
    
    @staticmethod
    def composite_datamatrix(original_img_path, new_datamatrix, bbox, output_path):
        """
        Composite new Data Matrix back into original image
        """
        try:
            # Read original image
            img = cv2.imread(original_img_path)
            if img is None:
                raise ValueError("❌ Could not read original image")
            
            x, y, w, h = bbox
            
            # Ensure new datamatrix is same size as bbox
            if new_datamatrix.shape[:2] != (h, w):
                new_dm_resized = cv2.resize(new_datamatrix, (w, h), interpolation=cv2.INTER_NEAREST)
            else:
                new_dm_resized = new_datamatrix
            
            # Ensure binary
            _, new_dm_binary = cv2.threshold(new_dm_resized, 127, 255, cv2.THRESH_BINARY)
            
            # Replace the region
            if len(img.shape) == 3:  # Color image
                new_dm_3ch = cv2.cvtColor(new_dm_binary, cv2.COLOR_GRAY2BGR)
                img[y:y+h, x:x+w] = new_dm_3ch
            else:  # Grayscale
                img[y:y+h, x:x+w] = new_dm_binary
            
            # Save output
            cv2.imwrite(output_path, img)
            print(f"✅ Data Matrix composited successfully! Output: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Error compositing Data Matrix: {e}")
            return None
    
    @staticmethod
    def regenerate_datamatrix_on_label(image_path, new_postcode, new_building_name, output_path):
        """
        Complete pipeline: decode → update → regenerate → composite
        """
        print("=" * 50)
        print("🔄 Regenerating Data Matrix on Label")
        print("=" * 50)
        
        try:
            # Step 1: Detect and decode existing Data Matrix
            print("\n📌 Step 1: Decoding existing Data Matrix...")
            decoded, bbox, img = DataMatrixProcessor.detect_datamatrix(image_path)
            payload = DataMatrixProcessor.decode_payload(decoded)
            
            print(f"   Old Payload: {payload[:50]}...")
            
            # Step 2: Update payload with new address
            print("\n📌 Step 2: Updating payload...")
            new_payload = DataMatrixProcessor.update_payload(payload, new_postcode, new_building_name)
            print(f"   New Payload: {new_payload[:50]}...")
            
            # Step 3: Generate new Data Matrix
            print("\n📌 Step 3: Generating new Data Matrix...")
            new_dm = DataMatrixProcessor.generate_datamatrix(new_payload, (bbox[2], bbox[3]))
            
            if new_dm is None:
                raise ValueError("Failed to generate Data Matrix")
            
            # Step 4: Composite back
            print("\n📌 Step 4: Compositing back to label...")
            result = DataMatrixProcessor.composite_datamatrix(image_path, new_dm, bbox, output_path)
            
            if result:
                print("\n" + "=" * 50)
                print("✅ Data Matrix Regeneration Complete!")
                print(f"📁 Output: {output_path}")
                print("=" * 50)
                return result
            else:
                return None
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    @staticmethod
    def process_label(image_path):
        """
        Complete processing pipeline
        """
        print("=" * 50)
        print("🔍 Royal Mail Data Matrix Processing")
        print("=" * 50)
        
        try:
            # Step 1: Detect
            print("\n📌 Step 1: Detecting Data Matrix...")
            decoded, bbox, img = DataMatrixProcessor.detect_datamatrix(image_path)
            
            # Step 2: Decode
            print("\n📌 Step 2: Decoding payload...")
            payload = DataMatrixProcessor.decode_payload(decoded)
            
            # Step 3: Extract fields
            print("\n📌 Step 3: Extracting fields...")
            fields = DataMatrixProcessor.extract_fields(payload)
            
            # Step 4: Parse structure
            print("\n📌 Step 4: Parsing RM structure...")
            structure = DataMatrixProcessor.parse_rm_structure(payload)
            
            print("\n" + "=" * 50)
            print("✅ Processing Complete!")
            print("=" * 50)
            
            return {
                'payload': payload,
                'fields': fields,
                'structure': structure,
                'bbox': bbox
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return None