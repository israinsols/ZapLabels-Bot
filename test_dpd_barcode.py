import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image
import sys

image_path = r"C:\Users\ccslaptophyd\OneDrive\Desktop\ZapLabels-Bot\downloads\photo_8619429877.jpg"

img = cv2.imread(image_path)
if img is None:
    print("❌ Image not loaded")
    sys.exit(1)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape
print(f"📐 Image size: {w}x{h}")

strategies = [
    ('raw gray', gray),
    ('CLAHE', cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray)),
    ('Otsu', cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
    ('adaptive', cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)),
    ('2x upscale', cv2.resize(gray, (w*2, h*2), interpolation=cv2.INTER_CUBIC)),
    ('3x upscale', cv2.resize(gray, (w*3, h*3), interpolation=cv2.INTER_CUBIC)),
    ('inverted', cv2.bitwise_not(gray)),
    ('sharpened', cv2.filter2D(gray, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))),
    ('bottom half', gray[h//2:, :]),
    ('top half', gray[:h//2, :]),
    ('bottom quarter', gray[3*h//4:, :]),
    ('denoised', cv2.fastNlMeansDenoising(gray, h=10)),
]

found = False
for name, arr in strategies:
    decoded = pyzbar_decode(Image.fromarray(arr))
    if decoded:
        print(f"\n✅ FOUND with strategy: [{name}]")
        for code in decoded:
            try:
                data = code.data.decode('utf-8')
            except:
                data = code.data.decode('latin-1')
            print(f"   Type: {code.type}")
            print(f"   Data: {data[:100]}")
            print(f"   Rect: {code.rect}")
        found = True
        break
    else:
        print(f"   ❌ {name}: no barcode")

if not found:
    print("\n⚠️ No barcode detected with any strategy")
    print("💡 Possible reasons:")
    print("   - Image was sent as photo (Telegram compresses photos)")
    print("   - Send the label as a DOCUMENT/FILE instead of a photo")
    print("   - DPD label might use a format not supported by pyzbar")
