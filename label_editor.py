import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

class LabelEditor:
    
    @staticmethod
    def _get_font(bold=False, size=14):
        """Cross-platform font loader with fallback"""
        candidates = []
        if bold:
            candidates = [
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                "arialbd.ttf",
            ]
        else:
            candidates = [
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "arial.ttf",
            ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    @staticmethod
    def replace_ups_address(image_path, new_address_data, output_path):
        """
        Specialized UPS address replacer matching official UPS label typography and layout:
        - Detects real continuous outer black border lines (if present)
        - If borderless, clears flush from x=0 to w to completely eradicate any ghost characters
        - Preserves return address (top-left) and shipment metadata / weight (top-right) completely
        - Preserves horizontal divider line and barcode/routing section below
        - Formats SHIP TO block with authentic indentation and large bold City/State/Zip
        """
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor.replace_ups_address")
            return None
        
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Detect actual continuous vertical black border lines (if any)
        # A true border column must be at least 70% solid black (< 80) from top to bottom
        left_border_cols = [x for x in range(int(w * 0.1)) if np.mean(gray[:, x] < 80) > 0.70]
        x1 = (left_border_cols[-1] + 1) if left_border_cols else 0

        right_border_cols = [x for x in range(w - 1, int(w * 0.90), -1) if np.mean(gray[:, x] < 80) > 0.70]
        x2 = (right_border_cols[-1] - 1) if right_border_cols else w

        # 2. Detect divider line (horizontal line at ~28% to 42% height)
        _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w * 0.4), 1))
        lines_img = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        row_sums = np.sum(lines_img > 0, axis=1)
        line_y_indices = np.where(row_sums > w * 0.35)[0]

        divider_y = int(h * 0.353)
        for y in line_y_indices:
            if int(h * 0.28) <= y <= int(h * 0.42):
                divider_y = y
                break

        # 3. Detect gap below return address (around 9% to 14% height)
        top_sub = thresh[int(h * 0.02):divider_y, x1:int(w * 0.45)]
        row_activity = np.sum(top_sub > 0, axis=1)
        y_start = int(h * 0.115)
        for rel_y, act in enumerate(row_activity):
            actual_y = int(h * 0.02) + rel_y
            if act == 0 and int(h * 0.09) <= actual_y <= int(h * 0.13):
                y_start = actual_y
                break

        # 4. Find return address left alignment
        top_text = np.where(gray[int(h * 0.02):int(h * 0.10), x1:int(w * 0.45)] < 128)
        if len(top_text[1]) > 0:
            align_x = x1 + int(np.percentile(top_text[1], 1))
        else:
            align_x = x1 + (int(w * 0.052) if left_border_cols else int(w * 0.02))

        # 5. Clean whiteout box covering ONLY the SHIP TO section
        y1 = y_start + max(2, int(h * 0.005))
        y2 = divider_y - max(2, int(h * 0.003))

        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)

        # 6. Parse address components
        name = new_address_data.get('name') or new_address_data.get('company') or new_address_data.get('company_name', '')
        street = new_address_data.get('street', '')
        raw_addr = new_address_data.get('address') or new_address_data.get('address1', '')
        postcode = new_address_data.get('postcode') or new_address_data.get('zip', '')
        city = new_address_data.get('city', '')
        state = new_address_data.get('state', '')

        if not street and raw_addr:
            parts = [p.strip() for p in raw_addr.split(',') if p.strip()]
            if len(parts) >= 2 and not city:
                street = ', '.join(parts[:-1])
                city = parts[-1]
            else:
                street = raw_addr

        city_line_parts = []
        if city:
            city_line_parts.append(city.upper())
        if state:
            city_line_parts.append(state.upper())
        if postcode:
            city_line_parts.append(postcode.upper())
        city_state_zip = ' '.join(city_line_parts)

        # 7. Fonts scaled proportionally
        font_label = LabelEditor._get_font(bold=True, size=max(12, int(w * 0.034)))
        font_name = LabelEditor._get_font(bold=True, size=max(11, int(w * 0.030)))
        font_street = LabelEditor._get_font(bold=True, size=max(11, int(w * 0.028)))
        font_city = LabelEditor._get_font(bold=True, size=max(15, int(w * 0.043)))

        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)

        ship_to_x = align_x
        ship_to_y = y1 + int(h * 0.015)
        indent_x = align_x + max(14, int(w * 0.055))
        line_spacing = max(12, int(h * 0.020))

        # Line 1: SHIP TO:
        draw.text((ship_to_x, ship_to_y), 'SHIP TO:', fill='black', font=font_label)

        # Indented address lines
        cur_y = ship_to_y + int(h * 0.022)
        if name:
            draw.text((indent_x, cur_y), name.upper(), fill='black', font=font_name)
            cur_y += line_spacing

        if street:
            draw.text((indent_x, cur_y), street.upper(), fill='black', font=font_street)
            cur_y += line_spacing

        if city_state_zip:
            draw.text((indent_x, cur_y + max(2, int(h * 0.003))), city_state_zip, fill='black', font=font_city)

        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        print(f"✅ UPS Address replaced with exact sample format -> {output_path}")
        return output_path

    @staticmethod
    def replace_address_on_label(image_path, new_address_data, output_path):
        """
        Generic carrier address replacer (preserves borders and returns clean layout)
        """
        img = cv2.imread(image_path)
        if img is None:
            print("❌ Error: Image not found in LabelEditor")
            return None
        
        h, w = img.shape[:2]
        
        x1 = int(w * 0.08)
        y1 = int(h * 0.08)
        x2 = int(w * 0.92)
        y2 = int(h * 0.28)
        
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 255, 255), -1)
        
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        font_size = max(12, int(w * 0.025)) 
        font = LabelEditor._get_font(bold=False, size=font_size)
            
        name = new_address_data.get('name') or new_address_data.get('company_name', '')
        street = new_address_data.get('street') or new_address_data.get('address', '')
        city = new_address_data.get('city', '')
        postcode = new_address_data.get('postcode', '')
        
        lines = ["SHIP TO:"]
        if name:
            lines.append(name.upper())
        if street:
            lines.append(street.upper())
        if city or postcode:
            lines.append(f"{city.upper()} {postcode.upper()}".strip())
        
        address_text = "\n".join(lines)
        draw.multiline_text((x1 + 10, y1 + 10), address_text, fill="black", font=font, spacing=6)
        
        img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        cv2.imwrite(output_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
        print(f"✅ Address replaced cleanly.")
        return output_path
