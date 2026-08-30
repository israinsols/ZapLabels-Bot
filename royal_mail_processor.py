import os
import re
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract

import shutil

if shutil.which("tesseract"):
    pytesseract.pytesseract.tesseract_cmd = "tesseract"
elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"



def _open_image(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(path)
            page = doc[0]
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            doc.close()
            return img
        except Exception as e:
            raise RuntimeError(f"PDF open failed: {e}")
    else:
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"Cannot read image: {path}")
        return img


def _save_image(img, path):
    cv2.imwrite(path, img)


def _to_pil(img):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _from_pil(pil_img):
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def _get_font(size):
    """Cross-platform font loader: tries Arial on Windows and Liberation/DejaVu on Linux."""
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _ocr_full(img, psm=6):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray, config=f"--oem 3 --psm {psm}")


def _ocr_data(img, psm=6):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_data(
        gray,
        config=f"--oem 3 --psm {psm}",
        output_type=pytesseract.Output.DICT
    )


def _is_tracking(text):
    """Check if a string looks like a Royal Mail tracking number."""
    clean = re.sub(r'[^A-Z0-9]', '', text.upper())
    if len(clean) >= 9 and len(clean) <= 21:
        if re.match(r'^[A-Z]{2}[0-9]{8,14}[A-Z]{2}$', clean) or re.match(r'^[0-9]{9,21}$', clean):
            return True
    return False


def _alter_one_digit(tracking):
    """Alter the last digit of the tracking number by +1 (wraps 9 -> 0)."""
    for i in range(len(tracking) - 1, -1, -1):
        if tracking[i].isdigit():
            new_digit = str((int(tracking[i]) + 1) % 10)
            return tracking[:i] + new_digit + tracking[i + 1:]
    return tracking


def alter_tracking_text_on_image(img):
    """
    Locate the printed tracking number text (not the barcode bars),
    alter one digit, and paint the new text back over the original.
    """
    h_img, w_img = img.shape[:2]
    data = _ocr_data(img, psm=6)
    n = len(data["text"])
    
    # 1. Get words ONLY from middle section of label (30% to 65% height)
    # to avoid header text like 'Postage Paid GB' at top right
    words = []
    for i in range(n):
        w = data["text"][i].strip()
        if w:
            y1 = data["top"][i]
            y2 = y1 + data["height"][i]
            # Restrict to middle height zone where tracking text lives
            if y1 >= int(h_img * 0.30) and y2 <= int(h_img * 0.65):
                words.append({
                    "text": w,
                    "clean": re.sub(r'[^A-Z0-9]', '', w.upper()),
                    "x1": data["left"][i],
                    "y1": y1,
                    "x2": data["left"][i] + data["width"][i],
                    "y2": y2
                })
            
    full_clean = "".join([w["clean"] for w in words])
    tracking_clean = None
    
    m = re.search(r'[A-Z]{2}[0-9]{8,14}[A-Z]{2}', full_clean)
    if m: tracking_clean = m.group()
    else:
        m2 = re.search(r'[0-9]{11,21}', full_clean)
        if m2: tracking_clean = m2.group()
        
    if not tracking_clean:
        print("Could not find written tracking number in middle zone -- skipping alter step")
        return img
        
    # 2. Find which words in the middle zone make up this tracking number
    tracking_box = None
    original_text_parts = []
    
    for w in words:
        if len(w["clean"]) >= 2 and w["clean"] in tracking_clean:
            # It's part of the tracking number!
            original_text_parts.append(w["text"])
            if tracking_box is None:
                tracking_box = [w["x1"], w["y1"], w["x2"], w["y2"]]
            else:
                tracking_box[0] = min(tracking_box[0], w["x1"])
                tracking_box[1] = min(tracking_box[1], w["y1"])
                tracking_box[2] = max(tracking_box[2], w["x2"])
                tracking_box[3] = max(tracking_box[3], w["y2"])
                
    if not tracking_box:
        print("Found tracking string but couldn't locate words -- skipping alter step")
        return img
        
    tracking_found = " ".join(original_text_parts)
    print(f"Found tracking text: '{tracking_found}' at box {tracking_box}")

    altered = _alter_one_digit(tracking_found)
    print(f"Altered tracking: {tracking_found} -> {altered}")

    if tracking_box:
        x, y = tracking_box[0], tracking_box[1]
        bw, bh = tracking_box[2] - tracking_box[0], tracking_box[3] - tracking_box[1]
        
        # Add slight margin to box
        pad = 2
        x1_w = max(0, x - pad)
        y1_w = max(0, y - pad)
        x2_w = min(w_img, x + bw + pad)
        y2_w = min(h_img, y + bh + pad)

        # Wipe old text with white rectangle
        cv2.rectangle(img, (x1_w, y1_w), (x2_w, y2_w), (255, 255, 255), -1)
        
        # Render new text with PIL
        pil = _to_pil(img)
        draw = ImageDraw.Draw(pil)
        font_size = max(12, int(bh * 0.85))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text((x, y), altered, fill=(0, 0, 0), font=font)
        img = _from_pil(pil)

    return img


def _find_delivery_address_box(img):
    """
    Use horizontal divider line detection to find the delivery address zone.
    Falls back to OCR postcode detection if dividers not found.
    Returns (x1, y1, x2, y2) pixel coords.
    """
    h, w = img.shape[:2]

    # --- Strategy 1: Find horizontal divider lines (most reliable) ---
    dividers = _find_horizontal_dividers(img)
    # The delivery address sits in the LARGEST gap between consecutive mid-dividers
    mid_dividers = [y for y in dividers if int(h * 0.40) < y < int(h * 0.92)]
    if len(mid_dividers) >= 2:
        # Find the largest gap between consecutive dividers (= address section)
        best_top, best_bot, best_gap = mid_dividers[0], mid_dividers[1], 0
        for i in range(len(mid_dividers) - 1):
            gap = mid_dividers[i + 1] - mid_dividers[i]
            if gap > best_gap:
                best_gap = gap
                best_top = mid_dividers[i]
                best_bot = mid_dividers[i + 1]
        x1 = 5
        y1 = best_top + 5   # small buffer below the divider line
        x2 = w - 5
        y2 = best_bot - 2
        print(f"Address zone from dividers (largest gap): y={best_top}..{best_bot}")
        return x1, y1, x2, y2

    # --- Strategy 2: OCR postcode detection ---
    data = _ocr_data(img, psm=6)
    n = len(data["text"])
    candidate_boxes = []

    for i in range(n):
        text = data["text"][i].strip()
        if re.match(r"^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$", text.replace(' ', '')) or \
           re.match(r"^[A-Z]{1,2}[0-9][A-Z0-9]?\s[0-9][A-Z]{2}$", text):
            conf_raw = data["conf"][i]
            conf = int(conf_raw) if str(conf_raw).lstrip("-").isdigit() else 0
            if conf > 30:
                px = data["left"][i]
                py = data["top"][i]
                candidate_boxes.append((px, py, text))

    if not candidate_boxes:
        x1 = int(w * 0.02)
        y1 = int(h * 0.52)
        x2 = int(w * 0.98)
        y2 = int(h * 0.74)
        print("No postcode found by OCR -- using proportional fallback zone")
        return x1, y1, x2, y2

    best = sorted(candidate_boxes, key=lambda b: abs(b[1] - h * 0.60))[0]
    pc_x, pc_y, pc_text = best

    line_h = 30
    box_x1 = 5
    box_y1 = max(int(h * 0.50), pc_y - line_h * 6)
    box_x2 = w - 5
    box_y2 = min(h, pc_y + line_h * 2)
    print(f"Delivery address box (OCR): ({box_x1},{box_y1}) -> ({box_x2},{box_y2})  postcode={pc_text}")
    return box_x1, box_y1, box_x2, box_y2


def _find_horizontal_dividers(img):
    """
    Detect full-width horizontal divider lines in label image.
    Returns sorted list of y-positions where divider lines exist.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    row_black = np.sum(gray < 100, axis=1)
    dividers = []
    for y in range(h):
        if row_black[y] > w * 0.35:
            if not dividers or y - dividers[-1] > 10:
                dividers.append(y)
    return dividers


def _build_address_lines(warehouse):
    """Format warehouse dict into Royal Mail style address lines."""
    addr = warehouse.get("address", "")
    name = warehouse.get("name", "").strip()
    postcode = warehouse.get("postcode", "").strip().upper()
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    lines = [name] + parts + [postcode]
    return [l for l in lines if l]


def replace_delivery_address(img, warehouse):
    """Wipe old delivery address and write new 3PL address in matching style."""
    box = _find_delivery_address_box(img)
    if box is None:
        print("Could not locate delivery address box")
        return img
    x1, y1, x2, y2 = box
    box_h = y2 - y1

    # Wipe the old address completely (full width)
    cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)

    # Font size relative to box height
    num_lines = 5
    font_size = max(14, box_h // (num_lines + 2))
    lines = _build_address_lines(warehouse)

    pil = _to_pil(img)
    draw = ImageDraw.Draw(pil)
    font = _get_font(font_size)

    pad = 8
    ty = y1 + pad
    for line in lines:
        draw.text((x1 + pad, ty), line, fill=(0, 0, 0), font=font)
        ty += font_size + 8

    img = _from_pil(pil)
    print(f"Delivery address replaced: {lines}")
    return img


def wipe_sender_address(img):
    """
    Find and remove the sender / return address.
    Looks for 'From:' keywords. Does NOT fallback to wiping top-left corner
    because that corner often contains the Service Indicator (e.g. Tracked 24).
    """
    h, w = img.shape[:2]
    data = _ocr_data(img, psm=11)
    n = len(data["text"])
    found_y = None
    found_x = None

    sender_pattern = re.compile(r"^(from|sender)$", re.IGNORECASE)

    for i in range(n):
        text = data["text"][i].strip()
        if sender_pattern.match(text):
            conf_raw = data["conf"][i]
            conf = int(conf_raw) if str(conf_raw).lstrip("-").isdigit() else 0
            if conf > 40:
                found_y = data["top"][i]
                found_x = data["left"][i]
                print(f"Sender keyword found: '{text}' at y={found_y}")
                break

    if found_y is not None:
        y1 = max(0, found_y - 5)
        y2 = min(h, found_y + 130)
        x1 = max(0, found_x - 5)
        x2 = min(w, found_x + 380)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        print(f"Sender address wiped: ({x1},{y1})->({x2},{y2})")
    else:
        print("No sender keyword found -- NOT wiping anything (protecting Service Indicator).")

    return img


def wipe_bottom_references(img):
    """
    Erase extra order numbers, reference numbers, or symbols at the very bottom.
    Uses divider line detection to avoid wiping the 'Post Office / Internal use' banner.
    """
    h, w = img.shape[:2]

    # Use divider detection to find the bottom zone to wipe
    dividers = _find_horizontal_dividers(img)
    # The last divider in the lower 80-95% range is the bottom banner's top line
    banner_dividers = [y for y in dividers if int(h * 0.78) < y < int(h * 0.95)]

    if banner_dividers:
        # Wipe below the last divider (very bottom strip below the Post Office / Internal use box)
        wipe_y = banner_dividers[-1] + 2
    else:
        wipe_y = int(h * 0.88)

    # Check if there's text/symbols below banner line (e.g., order ref symbols)
    data = _ocr_data(img, psm=6)
    n = len(data["text"])
    has_bottom_data = False
    for i in range(n):
        if data["text"][i].strip():
            if data["top"][i] >= wipe_y:
                has_bottom_data = True
                break

    if has_bottom_data:
        cv2.rectangle(img, (0, wipe_y), (w, h), (255, 255, 255), -1)
        print(f"Bottom reference numbers wiped from y={wipe_y} to y={h}")
    else:
        print("No extra bottom reference text found -- preserving bottom section.")

    # Also wipe any stray symbols inside the address block right side (e.g. $IoI reference)
    # These appear inside the address zone on the right side bottom
    addr_dividers = [y for y in dividers if int(h * 0.40) < y < int(h * 0.85)]
    if len(addr_dividers) >= 2:
        gaps = [(addr_dividers[i+1] - addr_dividers[i], addr_dividers[i], addr_dividers[i+1])
                for i in range(len(addr_dividers)-1)]
        largest = max(gaps, key=lambda g: g[0])
        _, top_addr, bot_addr = largest
        # Wipe bottom-right quadrant of address section (where reference symbols appear)
        sym_y1 = bot_addr - int((bot_addr - top_addr) * 0.3)
        sym_x1 = int(w * 0.55)
        cv2.rectangle(img, (sym_x1, sym_y1), (w, bot_addr), (255, 255, 255), -1)
        print(f"Wiped stray symbols in address block bottom-right: x={sym_x1}..{w}, y={sym_y1}..{bot_addr}")

    return img


def update_datamatrix(img, input_img_or_path, warehouse):
    """
    Decode existing Royal Mail DataMatrix -> update postcode + building name
    -> regenerate at same size -> composite back onto label.
    Reads from input_img_or_path (the ORIGINAL image or path) to guarantee it hasn't been wiped.
    """
    from datamatrix_processor import DataMatrixProcessor

    try:
        # DETECT FROM THE ORIGINAL IMAGE
        print("Detecting DataMatrix on original label...")
        decoded, bbox, _ = DataMatrixProcessor.detect_datamatrix(input_img_or_path)
        payload = DataMatrixProcessor.decode_payload(decoded)
        
        new_postcode = warehouse.get("postcode", "").strip()
        new_building = warehouse.get("name", "").strip()
        new_payload = DataMatrixProcessor.update_payload(payload, new_postcode, new_building)
        
        # Generate new DataMatrix
        new_dm = DataMatrixProcessor.generate_datamatrix(new_payload, (bbox[2], bbox[3]))

        if new_dm is not None:
            x, y, bw, bh = bbox

            # Wipe old DataMatrix and any surrounding dotted frame completely with white
            pad_x = max(6, int(bw * 0.10))
            pad_y = max(6, int(bh * 0.10))
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(img.shape[1], x + bw + pad_x)
            y2 = min(img.shape[0], y + bh + pad_y)
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)

            if len(img.shape) == 3:
                new_dm_3ch = cv2.cvtColor(new_dm, cv2.COLOR_GRAY2BGR)
                if new_dm_3ch.shape[:2] != (bh, bw):
                    new_dm_3ch = cv2.resize(new_dm_3ch, (bw, bh), interpolation=cv2.INTER_NEAREST)
                img[y:y + bh, x:x + bw] = new_dm_3ch
            else:
                if new_dm.shape[:2] != (bh, bw):
                    new_dm = cv2.resize(new_dm, (bw, bh), interpolation=cv2.INTER_NEAREST)
                img[y:y + bh, x:x + bw] = new_dm
            print(f"✅ DataMatrix updated at ({x},{y}) size {bw}x{bh}")
        else:
            print("⚠️ DataMatrix generation failed -- keeping original")

    except Exception as e:
        print(f"DataMatrix update error: {e}")
        # Fallback: Locate top-left 2D barcode box and place standard DataMatrix
        try:
            h_img, w_img = img.shape[:2]
            # Standard Royal Mail 2D barcode location: x=80, y=480 on 1146x1626 or proportional
            fx = int(w_img * 0.07)
            fy = int(h_img * 0.30)
            fw = int(w_img * 0.22)
            fh = int(h_img * 0.16)

            new_postcode = warehouse.get("postcode", "M1 1AE").strip()
            new_building = warehouse.get("name", "3PL HUB").strip()
            fallback_payload = f"JGB 6209H20B051414600004A759074       0050826050826TSS01  OT794438106GB {new_building.upper()} {new_postcode.upper()} 9ZGB N136AN"
            new_dm = DataMatrixProcessor.generate_datamatrix(fallback_payload, (fw, fh))
            if new_dm is not None:
                new_dm_3ch = cv2.cvtColor(new_dm, cv2.COLOR_GRAY2BGR)
                img[fy:fy + fh, fx:fx + fw] = new_dm_3ch
                print(f"✅ Fallback DataMatrix applied at ({fx},{fy}) size {fw}x{fh}")
        except Exception as inner_e:
            print(f"Fallback DataMatrix error: {inner_e}")

    return img


# ============================================================
# Main Processor Class
# ============================================================

class RoyalMailProcessor:
    """
    Royal Mail FTID — Direct Edit Pipeline.
    """

    @staticmethod
    def process_royal_mail_label(input_path, warehouse, output_path):
        print("=" * 55)
        print("Royal Mail FTID -- Direct Edit Pipeline")
        print("=" * 55)

        try:
            print("\nStep 1: Loading label...")
            img = _open_image(input_path)
            orig_img = img.copy()  # Pristine copy for barcode decoding
            h, w = img.shape[:2]
            print(f"   Dimensions: {w}x{h}px")

            print("\nStep 2: Altering written tracking number...")
            img = alter_tracking_text_on_image(img)

            print("\nStep 3: Replacing delivery address with 3PL...")
            img = replace_delivery_address(img, warehouse)

            print("\nStep 4: Wiping sender address...")
            img = wipe_sender_address(img)

            print("\nStep 5: Wiping bottom references + barcodes...")
            img = wipe_bottom_references(img)

            print("\nStep 6: Updating DataMatrix barcode...")
            img = update_datamatrix(img, orig_img, warehouse)

            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            _save_image(img, output_path)
            print(f"\nDone! Output saved: {output_path}")
            print("=" * 55)

            return {"output_path": output_path, "warehouse": warehouse}

        except Exception as e:
            print(f"RoyalMailProcessor error: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def extract_postcode_ocr(image_path):
        try:
            img = _open_image(image_path)
            text = _ocr_full(img, psm=6)
            matches = re.findall(r"[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}", text)
            if matches:
                return matches[0]
        except Exception as e:
            print(f"Postcode OCR error: {e}")
        return None
