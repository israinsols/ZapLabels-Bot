import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re
import os

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


class DPDProcessor:

    # ──────────────────────────────────────────────
    # STEP 1: Detect & decode barcode
    # ──────────────────────────────────────────────
    @staticmethod
    def detect_barcode(image_path):
        """
        Detect Code128 / PDF417 barcode on a DPD label using multiple
        preprocessing strategies to handle low-res / compressed images.
        Returns (list[dict], numpy BGR image)
        """
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"❌ Image not found or invalid: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        def _try_decode(arr):
            pil = Image.fromarray(arr)
            return pyzbar_decode(pil)

        def _extract(decoded):
            barcodes = []
            for code in decoded:
                try:
                    data = code.data.decode('utf-8')
                except UnicodeDecodeError:
                    data = code.data.decode('latin-1')
                barcodes.append({
                    'type': code.type,
                    'data': data,
                    'position': (code.rect.left, code.rect.top,
                                 code.rect.width, code.rect.height)
                })
                print(f"✅ Barcode detected: {code.type} → {data[:60]}{'...' if len(data) > 60 else ''}")
            return barcodes

        strategies = []

        # 1. Raw grayscale
        strategies.append(('raw gray', gray))

        # 2. CLAHE contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        strategies.append(('CLAHE', clahe.apply(gray)))

        # 3. Binary threshold (Otsu)
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        strategies.append(('Otsu threshold', otsu))

        # 4. Adaptive threshold
        adaptive = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        strategies.append(('adaptive threshold', adaptive))

        # 5. Upscale 2x (helps with small barcodes)
        upscaled = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        strategies.append(('2x upscale', upscaled))

        # 6. Inverted (some scanners work better with white-on-black)
        strategies.append(('inverted', cv2.bitwise_not(gray)))

        # 7. Sharpened
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        strategies.append(('sharpened', sharpened))

        # 8. Scan bottom-half of image only (DPD barcode usually at bottom)
        bottom_half = gray[h // 2:, :]
        strategies.append(('bottom half', bottom_half))

        # 9. Scan top-half
        top_half = gray[:h // 2, :]
        strategies.append(('top half', top_half))

        for name, arr in strategies:
            print(f"   🔍 Trying strategy: {name}...")
            decoded = _try_decode(arr)
            if decoded:
                print(f"   ✅ Found barcode with strategy: {name}")
                return _extract(decoded), img

        raise ValueError("❌ No barcode found in image after all strategies")


    # ──────────────────────────────────────────────
    # STEP 2: Extract tracking number
    # ──────────────────────────────────────────────
    @staticmethod
    def extract_tracking(barcode_data):
        """
        Extract DPD tracking number from barcode data.
        DPD tracking numbers are typically 14 digits, but we also handle
        JD-prefixed and shorter formats.
        """
        # Try 14-digit DPD format first
        match = re.search(r'\d{14}', barcode_data)
        if match:
            tracking = match.group()
            print(f"📦 Tracking number: {tracking}")
            return tracking

        # Try JD-prefixed format (JD000xxxxxxxxxx)
        match = re.search(r'JD\d{12,}', barcode_data)
        if match:
            tracking = match.group()
            print(f"📦 Tracking number (JD): {tracking}")
            return tracking

        # Fallback: any long digit sequence
        match = re.search(r'\d{10,}', barcode_data)
        if match:
            tracking = match.group()
            print(f"📦 Tracking number (fallback): {tracking}")
            return tracking

        print("⚠️ Tracking number not found")
        return None

    # ──────────────────────────────────────────────
    # STEP 3: Extract delivery postcode via OCR
    # ──────────────────────────────────────────────
    @staticmethod
    def extract_postcode_ocr(image_path):
        """
        Run Tesseract OCR on the label and pull out the UK delivery postcode.
        """
        img = cv2.imread(image_path)
        if img is None:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        text = pytesseract.image_to_string(gray, config='--oem 3 --psm 6')

        postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        matches = re.findall(postcode_pattern, text.upper())

        if matches:
            postcode = matches[0]
            print(f"📮 OCR Postcode: {postcode}")
            return postcode

        print("⚠️ No postcode found via OCR")
        return None

    # ──────────────────────────────────────────────
    # STEP 4: Replace address block on label
    # ──────────────────────────────────────────────
    @staticmethod
    def replace_address(image_path, warehouse, output_path):
        """
        Whiteout the existing address area (detected by OCR bounding boxes)
        and draw the new 3PL warehouse address in its place.
        """
        img = cv2.imread(image_path)
        if img is None:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Get bounding boxes for each word
        data = pytesseract.image_to_data(
            gray, config='--oem 3 --psm 6',
            output_type=pytesseract.Output.DICT
        )

        postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        postcode_found_idx = None

        for i, word in enumerate(data['text']):
            if re.search(postcode_pattern, word.upper()):
                postcode_found_idx = i
                break

        # Determine address block region — estimate from postcode box
        if postcode_found_idx is not None:
            px = data['left'][postcode_found_idx]
            py = data['top'][postcode_found_idx]
            ph = data['height'][postcode_found_idx]

            # Address block: assume ~5 lines above the postcode, same x
            block_top    = max(0, py - ph * 6)
            block_bottom = py + ph * 2
            block_left   = max(0, px - 20)
            block_right  = min(img.shape[1], px + 400)

            # Whiteout
            img[block_top:block_bottom, block_left:block_right] = 255

            # Draw new address using PIL (better font rendering)
            img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)

            # Try to load a font; fall back to default
            try:
                font = ImageFont.truetype("arial.ttf", size=max(14, ph))
                font_small = ImageFont.truetype("arial.ttf", size=max(12, ph - 2))
            except Exception:
                font = ImageFont.load_default()
                font_small = font

            new_addr = warehouse.get('address', '')
            city_part = new_addr.split(',')[1].strip() if ',' in new_addr else 'London'

            lines = [
                warehouse.get('name', ''),
                new_addr.split(',')[0].strip(),
                city_part,
                warehouse.get('postcode', ''),
            ]

            y_cursor = block_top + 4
            for line in lines:
                if line:
                    draw.text((block_left + 4, y_cursor), line,
                              fill=(0, 0, 0), font=font_small)
                    y_cursor += ph + 2

            img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        else:
            print("⚠️ Could not locate address region; saving original with note")

        cv2.imwrite(output_path, img)
        print(f"✅ Address replaced and saved: {output_path}")
        return output_path

    # ──────────────────────────────────────────────
    # STEP 5: Regenerate barcode with new postcode
    # ──────────────────────────────────────────────
    @staticmethod
    def regenerate_barcode(image_path, barcodes, new_postcode, output_path):
        """
        Replace the barcode on the label with a regenerated one containing
        the updated postcode.  Supports Code128 and PDF417.
        """
        if not barcodes:
            print("⚠️ No barcode info to regenerate")
            return output_path  # return as-is

        img = cv2.imread(output_path)   # work on the already-address-replaced image
        if img is None:
            img = cv2.imread(image_path)

        primary = barcodes[0]
        barcode_type = primary['type']
        old_data     = primary['data']
        x, y, w, h  = primary['position']

        # Update postcode in barcode data
        postcode_pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        new_data = re.sub(postcode_pattern, new_postcode, old_data, count=1)

        print(f"   Barcode type : {barcode_type}")
        print(f"   Old data     : {old_data[:80]}")
        print(f"   New data     : {new_data[:80]}")

        try:
            if barcode_type in ('CODE128', 'CODE39'):
                barcode_img = DPDProcessor._generate_code128(new_data, w, h)
            elif barcode_type == 'PDF417':
                barcode_img = DPDProcessor._generate_pdf417(new_data, w, h)
            else:
                # Fallback to Code128 for unknown types
                barcode_img = DPDProcessor._generate_code128(new_data, w, h)

            if barcode_img is not None:
                # Composite back onto label
                barcode_bgr = cv2.cvtColor(
                    np.array(barcode_img.convert('RGB')), cv2.COLOR_RGB2BGR
                )
                barcode_bgr = cv2.resize(barcode_bgr, (w, h), interpolation=cv2.INTER_NEAREST)
                img[y:y+h, x:x+w] = barcode_bgr
                print(f"✅ Barcode regenerated ({barcode_type})")
            else:
                print("⚠️ Barcode generation returned None; skipping replacement")

        except Exception as e:
            print(f"⚠️ Barcode regeneration failed: {e}")

        cv2.imwrite(output_path, img)
        return output_path

    # ──────────────────────────────────────────────
    # Internal helpers: barcode generators
    # ──────────────────────────────────────────────
    @staticmethod
    def _generate_code128(data, width, height):
        """Generate a Code128 barcode as PIL Image."""
        try:
            from barcode import Code128
            from barcode.writer import ImageWriter
            import io

            writer = ImageWriter()
            barcode_obj = Code128(data, writer=writer)
            buf = io.BytesIO()
            barcode_obj.write(buf, options={
                'write_text': False,
                'quiet_zone': 1,
                'module_height': max(10.0, height / 10.0),
            })
            buf.seek(0)
            img = Image.open(buf).convert('L')
            return img
        except ImportError:
            # python-barcode not installed — draw a simple placeholder
            print("⚠️ python-barcode not installed; using placeholder barcode")
            return DPDProcessor._placeholder_barcode(width, height)
        except Exception as e:
            print(f"⚠️ Code128 generation error: {e}")
            return None

    @staticmethod
    def _generate_pdf417(data, width, height):
        """Generate a PDF417 barcode as PIL Image."""
        try:
            from pdf417 import encode as pdf417_encode, render_image
            codes = pdf417_encode(data)
            img = render_image(codes, scale=2, ratio=3)
            return img.convert('L')
        except ImportError:
            print("⚠️ pdf417 library not installed; falling back to Code128")
            return DPDProcessor._generate_code128(data, width, height)
        except Exception as e:
            print(f"⚠️ PDF417 generation error: {e}")
            return None

    @staticmethod
    def _placeholder_barcode(width, height):
        """Simple black-and-white striped placeholder when no barcode lib available."""
        img = Image.new('L', (width, height), 255)
        draw = ImageDraw.Draw(img)
        bar_w = max(2, width // 40)
        for x in range(0, width, bar_w * 2):
            draw.rectangle([x, 0, x + bar_w, height], fill=0)
        return img

    # ──────────────────────────────────────────────
    # MAIN PIPELINE
    # ──────────────────────────────────────────────
    @staticmethod
    def process_dpd_label(image_path, warehouse, output_path):
        """
        Full DPD label processing pipeline:
        detect → extract tracking → replace address → regenerate barcode → save
        """
        print("=" * 50)
        print("📦 DPD Label Processing")
        print("=" * 50)

        try:
            # Step 1: Detect barcode
            print("\n📌 Step 1: Detecting barcode...")
            barcodes, img = DPDProcessor.detect_barcode(image_path)

            # Step 2: Extract tracking
            print("\n📌 Step 2: Extracting tracking number...")
            tracking = None
            if barcodes:
                tracking = DPDProcessor.extract_tracking(barcodes[0]['data'])

            # Step 3: Extract postcode via OCR (for warehouse lookup info)
            print("\n📌 Step 3: Extracting delivery postcode...")
            delivery_postcode = DPDProcessor.extract_postcode_ocr(image_path)

            # Step 4: Replace address
            print("\n📌 Step 4: Replacing delivery address...")
            DPDProcessor.replace_address(image_path, warehouse, output_path)

            # Step 5: Regenerate barcode with new postcode
            print("\n📌 Step 5: Regenerating barcode...")
            new_postcode = warehouse.get('postcode', delivery_postcode or 'E1 6AN')
            DPDProcessor.regenerate_barcode(image_path, barcodes, new_postcode, output_path)

            print("\n" + "=" * 50)
            print("✅ DPD Label Processing Complete!")
            print(f"📁 Output: {output_path}")
            print("=" * 50)

            return {
                'output_path': output_path,
                'tracking': tracking,
                'delivery_postcode': delivery_postcode,
                'new_postcode': new_postcode,
                'barcode_type': barcodes[0]['type'] if barcodes else 'Unknown',
            }

        except Exception as e:
            print(f"❌ DPD processing error: {e}")
            return None
