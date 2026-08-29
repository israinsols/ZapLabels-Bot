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
        
        scale = 1
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
            scale = 1
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
            decoded = decode(Image.fromarray(thresh))
        
        # Method 4: Try adaptive threshold
        if not decoded:
            scale = 1
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            decoded = decode(Image.fromarray(thresh))
        
        if not decoded:
            raise ValueError("❌ No Data Matrix found in image")
        
        # Get position (pylibdmtx top is measured from bottom of image, and adjust for scale)
        rect = decoded[0].rect
        x = int(rect.left / scale)
        top_from_bottom = int(rect.top / scale)
        w = int(rect.width / scale)
        h = int(rect.height / scale)
        y = img.shape[0] - top_from_bottom - h
        
        print(f"✅ Data Matrix detected at position: ({x}, {y}) size: {w}x{h} (scale={scale})")
        
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
        Generate new Data Matrix with updated payload.
        Uses integer-multiple scaling to avoid dotted/broken border artifacts.
        """
        try:
            # Encode payload
            encoded = encode(payload.encode('utf-8'))

            # Build grayscale array from encoded result
            if isinstance(encoded, Image.Image):
                img_gray = encoded.convert('L')
            elif hasattr(encoded, 'pixels') and hasattr(encoded, 'width'):
                img_rgb = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
                img_gray = img_rgb.convert('L')
            else:
                img_gray = Image.fromarray(np.array(encoded, dtype=np.uint8)).convert('L')

            full_arr = np.array(img_gray, dtype=np.uint8)

            # Binarise
            binary = np.where(full_arr > 127, 255, 0).astype(np.uint8)

            # Crop quiet zone — find bounding box of black pixels
            black_pixels = cv2.findNonZero(255 - binary)
            if black_pixels is not None:
                x, y, cw, ch = cv2.boundingRect(black_pixels)
                content = binary[y:y + ch, x:x + cw]
            else:
                content = binary

            target_w, target_h = size

            # Compute the largest INTEGER px-per-module that still fits inside target
            # with at least a 4px quiet zone on each side
            content_h, content_w = content.shape[:2]
            quiet = 4  # minimum quiet zone pixels
            max_scale_w = (target_w - 2 * quiet) / content_w
            max_scale_h = (target_h - 2 * quiet) / content_h
            scale = max(1, int(min(max_scale_w, max_scale_h)))

            # Scale content by integer factor — crisp, no fractional blur
            scaled_w = content_w * scale
            scaled_h = content_h * scale
            scaled = cv2.resize(content, (scaled_w, scaled_h), interpolation=cv2.INTER_NEAREST)
            scaled = np.where(scaled > 127, 255, 0).astype(np.uint8)

            # Pad to exact target size with white
            pad_top = (target_h - scaled_h) // 2
            pad_bottom = target_h - scaled_h - pad_top
            pad_left = (target_w - scaled_w) // 2
            pad_right = target_w - scaled_w - pad_left

            img_array = cv2.copyMakeBorder(
                scaled,
                pad_top, pad_bottom, pad_left, pad_right,
                cv2.BORDER_CONSTANT, value=255
            )

            print(f"✅ Data Matrix generated! Scale={scale}px/module, Content={scaled_w}x{scaled_h}, Final={img_array.shape}")
            return img_array

        except Exception as e:
            print(f"❌ Error generating Data Matrix: {e}")
            return None

    
    @staticmethod
    def update_payload(old_payload, new_postcode, new_building_name):
        """
        Cleanly replace building name + postcode — no duplicates.
        Everything between the tracking number and the old postcode is wiped
        and replaced with: new_building + new_postcode.
        """
        if not old_payload:
            return old_payload
        
        new_bldg = new_building_name.strip().upper()
        new_pc = new_postcode.strip().upper()
        
        # Find tracking number
        trk_match = re.search(r'[A-Z]{2}[0-9]{9}[A-Z]{2}', old_payload)
        if not trk_match:
            trk_match = re.search(r'[A-Z]{2}[0-9]{8,14}[A-Z]{2}', old_payload)
        
        if not trk_match:
            return old_payload
        
        pc_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}'
        
        # Prefer finding postcode AFTER the tracking number
        after_tracking = old_payload[trk_match.end():]
        pc_match = re.search(pc_pattern, after_tracking)
        
        if pc_match:
            # Postcode found after tracking — get absolute end index in full payload
            old_pc_abs_end = trk_match.end() + pc_match.end()
            prefix = old_payload[:trk_match.end()]
            suffix = old_payload[old_pc_abs_end:]
        else:
            # Fallback: search the full payload for any postcode
            pc_match_full = re.search(pc_pattern, old_payload)
            if pc_match_full:
                prefix = old_payload[:trk_match.end()]
                suffix = old_payload[pc_match_full.end():]
            else:
                # No postcode found anywhere — keep prefix, drop rest
                prefix = old_payload[:trk_match.end()]
                suffix = ''

        # Build clean payload — wipes ALL old text between tracking end and old postcode
        new_payload = f"{prefix} {new_bldg} {new_pc}{suffix}"

        print(f"✅ DataMatrix cleanly updated:")
        print(f"   Old: {old_payload}")
        print(f"   New: {new_payload}")
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