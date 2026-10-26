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
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.imwrite(path, img)

def _to_pil(img):
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

def _from_pil(pil_img):
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _get_font(size):
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
    clean = re.sub(r'[^A-Z0-9]', '', text.upper())
    if len(clean) >= 9 and len(clean) <= 21:
        if re.match(r'^[A-Z]{2}[0-9]{8,14}[A-Z]{2}$', clean) or re.match(r'^[0-9]{9,21}$', clean):
            return True
    return False

def _alter_one_digit(tracking):
    for i in range(len(tracking) - 1, -1, -1):
        if tracking[i].isdigit():
            new_digit = str((int(tracking[i]) + 1) % 10)
            return tracking[:i] + new_digit + tracking[i + 1:]
    return tracking

def _format_royal_mail_tracking(tracking):
    clean = re.sub(r'[^A-Z0-9]', '', str(tracking).upper())
    if len(clean) == 13 and clean[:2].isalpha():
        return f"#{clean[:2]} {clean[2:6]} {clean[6:10]} {clean[10:]}#"
    elif len(clean) >= 12:
        return f"#{clean[:2]} {clean[2:6]} {clean[6:10]} {clean[10:]}#"
    else:
        return f"#{clean}#"

def alter_tracking_text_on_image(img):
    h_img, w_img = img.shape[:2]
    true_tracking = None
    try:
        from datamatrix_processor import DataMatrixProcessor
        decoded_obj, _, _ = DataMatrixProcessor.detect_datamatrix(img)
        if decoded_obj:
            payload = decoded_obj.data.decode('utf-8', errors='ignore')
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

    altered = _alter_one_digit(true_tracking)
    formatted_tracking = _format_royal_mail_tracking(altered)
    print(f"Tracking altered: {true_tracking} -> {altered} (formatted: {formatted_tracking})")

    if tracking_box:
        x, y = tracking_box[0], tracking_box[1]
        bw, bh = tracking_box[2] - tracking_box[0], tracking_box[3] - tracking_box[1]
        center_x = x + bw // 2
        y_pos = y
    else:
        center_x = int(w_img * 0.63)
        y_pos = int(h_img * 0.48)
        bh = int(h_img * 0.03)
    pad_y = max(3, int(bh * 0.25))
    x1_w = max(0, min(center_x - 120, int(w_img * 0.38)))
    y1_w = max(0, y_pos - pad_y)
    x2_w = min(w_img - 6, max(center_x + 120, int(w_img * 0.88)))
    y2_w = min(h_img, y_pos + bh + pad_y)

    cv2.rectangle(img, (x1_w, y1_w), (x2_w, y2_w), (255, 255, 255), -1)

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
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    large_boxes = [cv2.boundingRect(c) for c in contours if cv2.boundingRect(c)[2] > w * 0.4 and cv2.boundingRect(c)[3] > h * 0.4]
    if large_boxes:
        bx, by, bw, bh = max(large_boxes, key=lambda b: b[2] * b[3])
        return bx, bx + bw
    return 0, w

def _find_delivery_address_box(img, orig_img=None):
    ref_img = orig_img if orig_img is not None else img
    h, w = ref_img.shape[:2]
    lb_left, lb_right = _get_label_bounds(ref_img)
    dividers = _find_horizontal_dividers(ref_img)
    mid_dividers = [y for y in dividers if int(h * 0.35) < y < int(h * 0.95)]
    if len(mid_dividers) >= 2:
        gaps = [(mid_dividers[i + 1] - mid_dividers[i], mid_dividers[i], mid_dividers[i + 1]) for i in range(len(mid_dividers) - 1)]
        best_gap, best_top, best_bot = max(gaps, key=lambda g: g[0])
        x1 = lb_left + 4
        y1 = best_top + 4
        x2 = lb_right - 4
        y2 = best_bot - 3
        return x1, y1, x2, y2

    data = _ocr_data(img, psm=6)
    n = len(data["text"])
    candidate_boxes = []
    for i in range(n):
        text = data["text"][i].strip()
        if re.match(r"^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$", text.replace(' ', '')) or re.match(r"^[A-Z]{1,2}[0-9][A-Z0-9]?\s[0-9][A-Z]{2}$", text):
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
        return x1, y1, x2, y2

    best = sorted(candidate_boxes, key=lambda b: abs(b[1] - h * 0.60))[0]
    pc_x, pc_y, pc_text = best
    line_h = 30
    box_x1 = 5
    box_y1 = max(int(h * 0.50), pc_y - line_h * 6)
    box_x2 = w - 5
    box_y2 = min(h, pc_y + line_h * 2)
    return box_x1, box_y1, box_x2, box_y2

def _find_horizontal_dividers(img):
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
    box = _find_delivery_address_box(img, orig_img=orig_img)
    if box is None:
        return img
    x1, y1, x2, y2 = box
    box_h = y2 - y1
    h, w = img.shape[:2]
    lb_left, lb_right = _get_label_bounds(img)
    x1_safe = max(6, x1)
    x2_safe = min(w - 6, x2)
    cv2.rectangle(img, (x1_safe, y1), (x2_safe, y2), (255, 255, 255), -1)
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
    return img

def wipe_sender_address(img):
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
                break
    if found_y is not None:
        y1 = max(0, found_y - 5)
        y2 = min(h, found_y + 130)
        x1 = max(0, found_x - 5)
        x2 = min(w, found_x + 380)
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
    return img

def wipe_bottom_references(img):
    h, w = img.shape[:2]
    dividers = _find_horizontal_dividers(img)
    banner_dividers = [y for y in dividers if int(h * 0.78) < y < int(h * 0.95)]
    if banner_dividers:
        wipe_y = banner_dividers[-1] + 2
    else:
        wipe_y = int(h * 0.88)

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

    addr_dividers = [y for y in dividers if int(h * 0.40) < y < int(h * 0.85)]
    if len(addr_dividers) >= 2:
        gaps = [(addr_dividers[i+1] - addr_dividers[i], addr_dividers[i], addr_dividers[i+1]) for i in range(len(addr_dividers)-1)]
        largest = max(gaps, key=lambda g: g[0])
        _, top_addr, bot_addr = largest
        sym_y1 = bot_addr - int((bot_addr - top_addr) * 0.3)
        sym_y2 = bot_addr - 3
        sym_x1 = int(lb_left + (lb_right - lb_left) * 0.55)
        sym_x2 = min(w - 6, lb_right - 4)
        cv2.rectangle(img, (sym_x1, sym_y1), (sym_x2, sym_y2), (255, 255, 255), -1)
    return img

def update_datamatrix(img, input_img_or_path, warehouse):
    from datamatrix_processor import DataMatrixProcessor
    try:
        decoded, bbox, _ = DataMatrixProcessor.detect_datamatrix(input_img_or_path)
        payload = DataMatrixProcessor.decode_payload(decoded)
        new_postcode = warehouse.get("postcode", "").strip()
        new_building = warehouse.get("name", "").strip()
        
        new_payload = DataMatrixProcessor.update_payload(payload, new_postcode, new_building)
        
        new_dm = DataMatrixProcessor.generate_datamatrix(new_payload, (bbox[2], bbox[3]))

        if new_dm is not None:
            x, y, bw, bh = bbox
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
                    new_dm = cv2.resize(new_dm, (bh, bw), interpolation=cv2.INTER_NEAREST)
                img[y:y + bh, x:x + bw] = new_dm
    except Exception as e:
        print(f"DataMatrix update error: {e}")
    return img

class RoyalMailProcessor:
    @staticmethod
    def process_royal_mail_label(input_path, warehouse, output_path):
        try:
            img = _open_image(input_path)
            orig_img = img.copy()
            
            img = alter_tracking_text_on_image(img)
            img = replace_delivery_address(img, warehouse, orig_img=orig_img)
            img = wipe_sender_address(img)
            img = wipe_bottom_references(img)
            img = update_datamatrix(img, orig_img, warehouse)

            h_out, w_out = img.shape[:2]
            bx1, by1, bx2, by2 = 3, 3, w_out - 4, h_out - 4
            cv2.rectangle(img, (bx1, by1), (bx2, by2), (0, 0, 0), 2)

            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            _save_image(img, output_path)
            return {"output_path": output_path, "warehouse": warehouse}
        except Exception as e:
            print(f"RoyalMailProcessor error: {e}")
            return None

    @staticmethod
    def extract_label_info(image_path):
        postcode = None
        try:
            img = _open_image(image_path)
            from datamatrix_processor import DataMatrixProcessor
            decoded_obj, _, _ = DataMatrixProcessor.detect_datamatrix(img)
            if decoded_obj:
                payload = decoded_obj.data.decode('utf-8', errors='ignore')
                matches = re.findall(r'([A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2})', payload)
                if matches:
                    postcode = matches[0]
            if not postcode:
                text = _ocr_full(img, psm=6)
                matches = re.findall(r"[A-Z]{1,2}[0-9][A-Z0-9]?\s?[0-9][A-Z]{2}", text)
                if matches:
                    postcode = matches[0]
        except Exception as e:
            pass
        return postcode, None

    @staticmethod
    def extract_postcode_ocr(image_path):
        pc, _ = RoyalMailProcessor.extract_label_info(image_path)
        return pc

    # ==========================================
    # NEW RTS FUNCTION (Solves RTS vs FTID issue)
    # ==========================================
    @staticmethod
    def process_rts_label(input_path, warehouse, output_path):
        """
        RTS (Return to Sender): Changes ONLY the return/sender address to the warehouse.
        Keeps the original delivery address exactly as it is.
        """
        try:
            img = _open_image(input_path)
            
            # Wipe ONLY sender address
            img = wipe_sender_address(img)
            
            h, w = img.shape[:2]
            font = _get_font(max(11, int(w * 0.033)))
            
            pil = _to_pil(img)
            draw = ImageDraw.Draw(pil)
            
            # Put warehouse address at the top-left (where sender/return address usually goes)
            lines = _build_address_lines(warehouse)
            start_y = int(h * 0.05)
            for line in lines:
                draw.text((int(w * 0.05), start_y), line, fill=(0, 0, 0), font=font)
                start_y += int(w * 0.045) 
                
            img = _from_pil(pil)
            
            # Add clean border
            h_out, w_out = img.shape[:2]
            cv2.rectangle(img, (3, 3), (w_out - 4, h_out - 4), (0, 0, 0), 2)
            
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            _save_image(img, output_path)
            
            print(f"✅ RTS Label Processed (Return Address Changed Only): {output_path}")
            return {"output_path": output_path, "warehouse": warehouse}
            
        except Exception as e:
            print(f"❌ RTS Processor error: {e}")
            return None