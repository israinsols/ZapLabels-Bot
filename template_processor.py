import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

from datamatrix_processor import DataMatrixProcessor

def _get_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


class RoyalMailTemplateProcessor:
    """
    Generates a Royal Mail label from scratch using a base template.
    Used for LIT mode, and for FTID mode when only a QR string is provided.
    """
    TEMPLATE_PATH = "templates/ROYAL_MAIL_EDITED_LIT.pdf"
    
    @staticmethod
    def generate_label(tracking_number, warehouse, output_path, service='FTID'):
        print("\n" + "=" * 55)
        print(f"Royal Mail Template Generation -- {service}")
        print("=" * 55)

        warehouse = warehouse or {}
        img_path = "templates/ROYAL_MAIL_EDITED_LIT.jpg"
        if not os.path.exists(img_path):
            print(f"❌ Template missing: {img_path}")
            return None

        img = cv2.imread(img_path)
        h, w = img.shape[:2]

        # Template coordinates based on inspection (300dpi):
        c128_box = (450, 520, 550, 190)
        dm_box = (80, 480, 260, 260)
        addr_box = (25, 840, 1100, 1150)
        track_text_box = (450, 720, 550, 100)
        
        # 1. WIPE OLD DATA
        cv2.rectangle(img, (c128_box[0], c128_box[1]), (c128_box[0]+c128_box[2], c128_box[1]+c128_box[3]), (255,255,255), -1)
        cv2.rectangle(img, (dm_box[0], dm_box[1]), (dm_box[0]+dm_box[2], dm_box[1]+dm_box[3]), (255,255,255), -1)
        cv2.rectangle(img, (addr_box[0], addr_box[1]), (addr_box[0]+addr_box[2], addr_box[1]+addr_box[3]), (255,255,255), -1)
        cv2.rectangle(img, (track_text_box[0], track_text_box[1]), (track_text_box[0]+track_text_box[2], track_text_box[1]+track_text_box[3]), (255,255,255), -1)
        
        # 2. GENERATE AND PLACE CODE128
        try:
            bc_class = barcode.get_barcode_class('code128')
            bc = bc_class(tracking_number, writer=ImageWriter())
            tmp_bc = f"{output_path}_tmp_bc"
            bc.save(tmp_bc, options={'write_text': False, 'module_height': 15, 'module_width': 0.4})
            
            bc_img = cv2.imread(f"{tmp_bc}.png")
            gray = cv2.cvtColor(bc_img, cv2.COLOR_BGR2GRAY)
            coords = cv2.findNonZero(255 - gray)
            x, y, bw, bh = cv2.boundingRect(coords)
            bc_cropped = bc_img[y:y+bh, x:x+bw]
            
            target_w, target_h = 519, 179
            bc_resized = cv2.resize(bc_cropped, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            
            img[534:534+target_h, 467:467+target_w] = bc_resized
            os.remove(f"{tmp_bc}.png")
            print("✅ Code128 applied")
        except Exception as e:
            print(f"❌ Error applying Code128: {e}")
            
        # 3. WRITE ALTERED TRACKING TEXT
        altered_tracking = tracking_number
        for i in range(len(altered_tracking) - 1, -1, -1):
            if altered_tracking[i].isdigit():
                new_digit = str((int(altered_tracking[i]) + 1) % 10)
                altered_tracking = altered_tracking[:i] + new_digit + altered_tracking[i+1:]
                break
                
        if len(altered_tracking) >= 13:
            p1, p2, p3, p4 = altered_tracking[:2], altered_tracking[2:6], altered_tracking[6:10], altered_tracking[10:]
            formatted_text = f"#{p1} {p2} {p3} {p4}#"
        else:
            formatted_text = altered_tracking
            
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        font = _get_font(36)
            
        text_x = 467 + (519 // 2) - 180
        text_y = 534 + 179 + 15
        draw.text((text_x, text_y), formatted_text, fill=(0,0,0), font=font)
        print(f"✅ Written tracking applied: {formatted_text} (Original: {tracking_number})")
        
        # 4. GENERATE AND PLACE DATAMATRIX
        try:
            new_postcode = warehouse.get("postcode", "IP32 7PF").strip().upper() if service == 'FTID' else "IP32 7PF"
            new_building = warehouse.get("name", "LIT HUB").upper() if service == 'FTID' else "LIT HUB"

            base_payload = "JGB 6209H20B051414600004A759074       0050826050826TSS01  OT794438106GB    NATIONAL DISTRUBITION CENTRE XX402HH 9ZGB N136AN"

            import re
            payload_str = re.sub(r'[A-Z]{2}[0-9]{9}[A-Z]{2}', tracking_number.upper(), base_payload, count=1)

            from datamatrix_processor import DataMatrixProcessor
            final_payload = DataMatrixProcessor.update_payload(payload_str, new_postcode, new_building)

            new_dm = DataMatrixProcessor.generate_datamatrix(final_payload, (235, 246))
            if new_dm is not None:
                # generate_datamatrix already returns the correct target size — no second resize needed
                new_dm_3ch = cv2.cvtColor(new_dm, cv2.COLOR_GRAY2BGR)
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                img[490:490+246, 92:92+235] = new_dm_3ch
                pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                print("✅ DataMatrix generated and placed")
            else:
                print("❌ DataMatrix generation failed")
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"❌ Error applying DataMatrix: {e}")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # 5. WRITE DELIVERY ADDRESS
        # Matched exactly to original template label text geometry and font (regular Arial 38px)
        draw = ImageDraw.Draw(pil_img)
        addr_font = _get_font(38)

        if service == 'FTID' and warehouse:
            name = warehouse.get("name", "").strip()
            addr = warehouse.get("address", "").strip()
            postcode = warehouse.get("postcode", "").strip().upper()
            parts = [p.strip() for p in addr.split(",") if p.strip()]
            if len(parts) >= 2:
                lines = [name, ", ".join(parts[:-1]), parts[-1], postcode]
            elif len(parts) == 1:
                lines = [name, parts[0], postcode]
            else:
                lines = [name, postcode]
        else:
            lines = ["LIT Hub", "Returns Centre", "Unit 1, London", "L1 1AA"]

        start_x = 38
        start_y = 848
        for line in lines:
            draw.text((start_x, start_y), line, fill=(0, 0, 0), font=addr_font)
            start_y += 50  # exact step matching original template lines

        print("✅ Address printed")

        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        
        out_dir = os.path.dirname(output_path)
        if out_dir: os.makedirs(out_dir, exist_ok=True)
        cv2.imwrite(output_path, img)
        print(f"✅ Template label saved to {output_path}")
        print("=" * 55)
        return output_path
