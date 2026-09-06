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


def _format_royal_mail_tracking(tracking):
    """Format Royal Mail tracking with clean standard spacing: #AA NNNN NNNN NGB#"""
    clean = re.sub(r'[^A-Z0-9]', '', str(tracking).upper())
    if len(clean) == 13 and clean[:2].isalpha():
        return f"#{clean[:2]} {clean[2:6]} {clean[6:10]} {clean[10:]}#"
    elif len(clean) >= 12:
        return f"#{clean[:2]} {clean[2:6]} {clean[6:10]} {clean[10:]}#"
    else:
        return f"#{clean}#"


def alter_tracking_text_on_image(img):
    """
    Locate the printed tracking number text under the Code128 barcode,
    alter one digit, and paint the new text back over the original.
    Works for both Tracked 24 (#OT794437107GB#) and Tracked 48 (#YR432371940609#) formats.
    """
    h_img, w_img = img.shape[:2]

    # 1. First, try to get the 100% complete true tracking number from DataMatrix payload
    true_tracking = None
    try:
        from datamatrix_processor import DataMatrixProcessor
        decoded_obj, _, _ = DataMatrixProcessor.detect_datamatrix(img)
        if decoded_obj:
            payload = decoded_obj.data.decode('utf-8', errors='ignore')
            # Standard Royal Mail 13-char tracking e.g. YR432371940GB or OT794438106GB
            m = re.search(r'([A-Z]{2}[0-9]{8,14}[A-Z]{2})', payload)
            if m and not m.group(1).startswith('GB') and not m.group(1).startswith('XX'):
                true_tracking = m.group(1)
            else:
                m2 = re.search(r'([A-Z]{2}[0-9]{8,14})', payload)
                if m2:
                    true_tracking = m2.group(1)
                else:
                    m3 = re.search(r'([0-9]{11,21})', payload)
                    if m3:
                        true_tracking = m3.group(1)
            if true_tracking:
                print(f"✅ Extracted pristine tracking from DataMatrix: {true_tracking}")
    except Exception as e:
        print(f"DataMatrix tracking extraction: {e}")

    # 2. Locate the tracking text box under the 1D barcode on the label
    data = _ocr_data(img, psm=6)
    n = len(data["text"])
    words = []
    tracking_box = None

    for i in range(n):
        w = data["text"][i].strip()
        if w:
            y1 = data["top"][i]
            y2 = y1 + data["height"][i]
            x1 = data["left"][i]
            x2 = x1 + data["width"][i]
            # Restrict strictly to zone below 1D barcode (40% to 58% height, right half of label)
            if y1 >= int(h_img * 0.40) and y2 <= int(h_img * 0.58) and x1 >= int(w_img * 0.30):
                clean = re.sub(r'[^A-Z0-9]', '', w.upper())
                words.append({"text": w, "clean": clean, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
                if '#' in w or (true_tracking and clean and len(clean) >= 2 and clean in true_tracking) or re.search(r'^[A-Z]{2}[0-9]|[0-9]{4,}', clean):
                    if tracking_box is None:
                        tracking_box = [x1, y1, x2, y2]
                    else:
                        tracking_box[0] = min(tracking_box[0], x1)
                        tracking_box[1] = min(tracking_box[1], y1)
                        tracking_box[2] = max(tracking_box[2], x2)
                        tracking_box[3] = max(tracking_box[3], y2)

    # If DataMatrix did not yield tracking, fallback to OCR words
    if not true_tracking:
        full_clean = "".join([w["clean"] for w in words])
        m = re.search(r'[A-Z]{2}[0-9]{8,14}[A-Z]{2}', full_clean)
        if m:
            true_tracking = m.group()
        else:
            m2 = re.search(r'[0-9]{9,21}', full_clean)
            if m2:
                true_tracking = m2.group()

    if not true_tracking:
        print("Could not find tracking number -- skipping alter step")
        return img

    # 3. Alter 1 digit and format cleanly
    altered = _alter_one_digit(true_tracking)
    formatted_tracking = _format_royal_mail_tracking(altered)
    print(f"Tracking altered: {true_tracking} -> {altered} (formatted: {formatted_tracking})")

    # 4. Position calculation
    if tracking_box:
        x, y = tracking_box[0], tracking_box[1]
        bw, bh = tracking_box[2] - tracking_box[0], tracking_box[3] - tracking_box[1]
        center_x = x + bw // 2
        y_pos = y
    else:
        center_x = int(w_img * 0.63)
        y_pos = int(h_img * 0.48)
        pad_y = max(3, int(bh * 0.25))
    x1_w = max(0, min(center_x - 120, int(w_img * 0.38)))
    y1_w = max(0, y_pos - pad_y)
    x2_w = min(w_img - 6, max(center_x + 120, int(w_img * 0.88)))
    y2_w = min(h_img, y_pos + bh + pad_y)

    cv2.rectangle(img, (x1_w, y1_w), (x2_w, y2_w), (255, 255, 255), -1)

    # 6. Render new tracking text centered with matching size
    pil = _to_pil(img)
    draw = ImageDraw.Draw(pil)
    font_size = max(13, int(w_img * 0.032))
    font = _get_font(font_size)

    bbox = draw.textbbox((0, 0), formatted_tracking, font=font)
    text_w = bbox[2] - bbox[0]
    draw_x = max(0, center_x - text_w // 2)

    draw.text((draw_x, y_pos), formatted_tracking, fill=(0, 0, 0), font=font)
    img = _from_pil(pil)

    return img



def _get_label_bounds(img):
    """
    Detect the left and right X boundaries of the white label card (in case of screenshots with dark margins).
    Returns (left_x, right_x).
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape

    # Check for large white region (label body)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    large_boxes = [cv2.boundingRect(c) for c in contours if cv2.boundingRect(c)[2] > w * 0.4 and cv2.boundingRect(c)[3] > h * 0.4]
    if large_boxes:
        bx, by, bw, bh = max(large_boxes, key=lambda b: b[2] * b[3])
        return bx, bx + bw

    return 0, w


def _find_delivery_address_box(img, orig_img=None):
    """
    Use horizontal divider line detection on pristine image to find the delivery address zone.
    Falls back to OCR postcode detection if dividers not found.
    Returns (x1, y1, x2, y2) pixel coords.
    """
    ref_img = orig_img if orig_img is not None else img
    h, w = ref_img.shape[:2]
    lb_left, lb_right = _get_label_bounds(ref_img)

    # --- Strategy 1: Find horizontal divider lines on pristine image ---
    dividers = _find_horizontal_dividers(ref_img)
    # The delivery address sits in the LARGEST gap between consecutive mid-dividers
    mid_dividers = [y for y in dividers if int(h * 0.35) < y < int(h * 0.95)]
    if len(mid_dividers) >= 2:
        gaps = [(mid_dividers[i + 1] - mid_dividers[i], mid_dividers[i], mid_dividers[i + 1]) for i in range(len(mid_dividers) - 1)]
        best_gap, best_top, best_bot = max(gaps, key=lambda g: g[0])
        x1 = lb_left + 4
        y1 = best_top + 4   # small buffer below the divider line
        x2 = lb_right - 4
        y2 = best_bot - 3   # keep bottom divider line intact
        print(f"Address zone from dividers (largest gap): x={x1}..{x2}, y={best_top}..{best_bot} (height={best_gap})")
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
    Uses gray < 160 to reliably detect light gray, anti-aliased, and standard divider lines.
    Returns sorted list of y-positions where divider lines exist.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    row_dark = np.sum(gray < 160, axis=1)
    dividers = []
    for y in range(h):
        if row_dark[y] > w * 0.45:
            if not dividers or y - dividers[-1] > 15:
                dividers.append(y)
    return dividers


def _build_address_lines(warehouse):
    """Format warehouse dict into authentic Royal Mail style address lines (3-4 lines)."""
    name = warehouse.get("name", "").strip()
    addr = warehouse.get("address", "").strip()
    postcode = warehouse.get("postcode", "").strip().upper()

    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) >= 2:
        street = ", ".join(parts[:-1])
        city = parts[-1]
        lines = [name, street, city, postcode]
    elif len(parts) == 1:
        lines = [name, parts[0], postcode]
    else:
        lines = [name, postcode]

    return [l for l in lines if l]


def replace_delivery_address(img, warehouse, orig_img=None):
    """Wipe old delivery address and write new 3PL address in matching style."""
    box = _find_delivery_address_box(img, orig_img=orig_img)
    if box is None:
        print("Could not locate delivery address box")
        return img
    x1, y1, x2, y2 = box
    box_h = y2 - y1
    h, w = img.shape[:2]
    lb_left, lb_right = _get_label_bounds(img)

    # Wipe the old address safely inside borders
    x1_safe = max(6, x1)
    x2_safe = min(w - 6, x2)
    cv2.rectangle(img, (x1_safe, y1), (x2_safe, y2), (255, 255, 255), -1)

    # Font size proportional to label width (matching authentic Royal Mail 1:1)
    font_size = max(11, int(w * 0.033))
    font = _get_font(font_size)
    line_step = int(font_size * 1.38)
    lines = _build_address_lines(warehouse)

    pil = _to_pil(img)
    draw = ImageDraw.Draw(pil)

    start_x = lb_left + max(8, int((lb_right - lb_left) * 0.024))
    start_y = y1 + max(8, int(box_h * 0.07))

    for line in lines:
        draw.text((start_x, start_y), line, fill=(0, 0, 0), font=font)
        start_y += line_step

    img = _from_pil(pil)
    print(f"Delivery address replaced with matching style: {lines}")
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

    lb_left, lb_right = _get_label_bounds(img)
    if has_bottom_data:
        x1_wipe = max(6, lb_left + 4)
        x2_wipe = min(w - 6, lb_right - 4)
        y2_wipe = h - 6
        cv2.rectangle(img, (x1_wipe, wipe_y), (x2_wipe, y2_wipe), (255, 255, 255), -1)
        print(f"Bottom reference numbers wiped: x={x1_wipe}..{x2_wipe}, y={wipe_y}..{y2_wipe}")
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
        lb_left, lb_right = _get_label_bounds(img)
        # Wipe bottom-right quadrant of address section (strictly above bottom divider line)
        sym_y1 = bot_addr - int((bot_addr - top_addr) * 0.3)
        sym_y2 = bot_addr - 3
        sym_x1 = int(lb_left + (lb_right - lb_left) * 0.55)
        sym_x2 = min(w - 6, lb_right - 4)
        cv2.rectangle(img, (sym_x1, sym_y1), (sym_x2, sym_y2), (255, 255, 255), -1)
        print(f"Wiped stray symbols in address block bottom-right: x={sym_x1}..{sym_x2}, y={sym_y1}..{sym_y2}")

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
            img = replace_delivery_address(img, warehouse, orig_img=orig_img)

            print("\nStep 4: Wiping sender address...")
            img = wipe_sender_address(img)

            print("\nStep 5: Wiping bottom references + barcodes...")
            img = wipe_bottom_references(img)

            print("\nStep 6: Updating DataMatrix barcode...")
            img = update_datamatrix(img, orig_img, warehouse)

            # Ensure clean outer rectangular border on label card
            lb_left, lb_right = _get_label_bounds(img)
            cv2.rectangle(img, (lb_left, 0), (lb_right - 1, img.shape[0] - 1), (0, 0, 0), 2)

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
    def extract_label_info(image_path):
        """Extract delivery postcode and original recipient name from DataMatrix or OCR."""
        postcode = None
        orig_name = None
        try:
            img = _open_image(image_path)
            # 1. Try DataMatrix first (highest reliability)
            try:
                from datamatrix_processor import DataMatrixProcessor
                decoded_obj, _, _ = DataMatrixProcessor.detect_datamatrix(img)
                if decoded_obj:
                    payload = decoded_obj.data.decode('utf-8', errors='ignore')
                    matches = re.findall(r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})', payload)
                    if matches:
                        postcode = matches[0]
                    m_name = re.search(r'[A-Z]{2}[0-9]{8,14}[A-Z]{2}\s+([A-Z\s]{4,30})\s+[A-Z0-9]{5,8}', payload)
                    if m_name:
                        orig_name = m_name.group(1).strip()
            except Exception as dm_e:
                print(f"DataMatrix info extract: {dm_e}")

            # 2. Fallback to OCR on image
            if not postcode:
                text = _ocr_full(img, psm=6)
                matches = re.findall(r"[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}", text)
                if matches:
                    postcode = matches[0]
        except Exception as e:
            print(f"Label info extract error: {e}")
        return postcode, orig_name

    @staticmethod
    def extract_postcode_ocr(image_path):
        pc, _ = RoyalMailProcessor.extract_label_info(image_path)
        return pc
