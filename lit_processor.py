import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import barcode
from barcode.writer import ImageWriter

class LITProcessor:
    
    TEMPLATES_PATH = "templates/"
    
    @staticmethod
    def get_template(carrier):
        """
        Carrier ke hisaab se template return karo
        Try both .png and .jpg extensions
        """
        templates = {
            'Royal Mail': ['royal_mail_lit.jpg', 'royal_mail_lit.png'],
            'DPD': ['dpd_lit.png', 'dpd_lit.jpg'],
            'UPS': ['ups_lit.png', 'ups_lit.jpg'],
            'Evri': ['evri_lit.png', 'evri_lit.jpg'],
            'DHL': ['dhl_lit.png', 'dhl_lit.jpg']
        }
        
        candidates = templates.get(carrier, ['default_lit.png'])
        for fname in candidates:
            full_path = os.path.join(LITProcessor.TEMPLATES_PATH, fname)
            if os.path.exists(full_path):
                print(f"   ✅ Template found: {full_path}")
                return fname
        
        # Fallback to default
        return 'default_lit.png'
    
    @staticmethod
    def apply_tracking_on_template(template_path, tracking_number, output_path):
        """
        Template par tracking number apply karo
        """
        img = Image.open(template_path).convert('RGB')
        
        # Get image size to calculate font size proportionally
        img_w, img_h = img.size
        font_size = max(20, img_w // 30)
        
        draw = ImageDraw.Draw(img)
        
        # Font settings
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Position for tracking — top area of template
        draw.text((img_w // 10, img_h // 8), tracking_number, fill="black", font=font)
        
        # Save as PNG always (to avoid JPEG re-compression issues in pipeline)
        img.save(output_path)
        print(f"✅ Tracking applied: {tracking_number}")
        return output_path
    
    @staticmethod
    def generate_barcode_for_lit(tracking_number, carrier, output_path):
        """
        LIT ke liye barcode generate karo
        """
        try:
            my_barcode = barcode.get('code128', tracking_number, writer=ImageWriter())
            barcode_path = f"{output_path}_barcode"
            my_barcode.save(barcode_path)
            print(f"✅ Barcode generated: {barcode_path}.png")
            return f"{barcode_path}.png"
        except Exception as e:
            print(f"❌ Error generating barcode: {e}")
            return None
    
    @staticmethod
    def process_lit(tracking_number, carrier, output_path):
        """
        Complete LIT processing pipeline
        """
        print("=" * 50)
        print(f"📦 LIT Mode — {carrier}")
        print("=" * 50)
        
        # Step 1: Get template
        template = LITProcessor.get_template(carrier)
        template_path = os.path.join(LITProcessor.TEMPLATES_PATH, template)
        
        if not os.path.exists(template_path):
            print(f"⚠️ Template not found: {template_path}, using default")
            template_path = os.path.join(LITProcessor.TEMPLATES_PATH, "default_lit.png")
            if not os.path.exists(template_path):
                print("❌ No template found at all!")
                return None
        
        print(f"\n📌 Step 2: Applying tracking text...")
        LITProcessor.apply_tracking_on_template(template_path, tracking_number, output_path)
        
        print(f"\n📌 Step 3: Generating barcode...")
        barcode_path = LITProcessor.generate_barcode_for_lit(tracking_number, carrier, output_path)
        
        print(f"\n📌 Step 4: Compositing barcode onto label...")
        if barcode_path and os.path.exists(barcode_path):
            try:
                main_img = Image.open(output_path).convert('RGB')
                barcode_img = Image.open(barcode_path).convert('RGB')
                
                img_w, img_h = main_img.size
                
                # Barcode: 60% of template width, height proportional
                bc_w = int(img_w * 0.6)
                bc_h = int(bc_w * 0.3)
                barcode_img = barcode_img.resize((bc_w, bc_h))
                
                # Place barcode at center-bottom area
                x = (img_w - bc_w) // 2
                y = int(img_h * 0.55)
                main_img.paste(barcode_img, (x, y))
                
                main_img.save(output_path)
                os.remove(barcode_path)
                print(f"✅ Barcode composited at ({x}, {y}), size ({bc_w}x{bc_h})")
            except Exception as e:
                print(f"❌ Error compositing barcode: {e}")
        
        print("\n" + "=" * 50)
        print("✅ LIT Label Created!")
        print(f"📁 Output: {output_path}")
        print("=" * 50)
        
        return output_path
