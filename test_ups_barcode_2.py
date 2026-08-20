import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image

image_path = r"C:\Users\ccslaptophyd\.gemini\antigravity\brain\bef353d3-a1e2-4528-bbbf-34b58af8dfd3\.user_uploaded\uploaded_media_1786802256206.png"
img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape

# Try to clean up the barcode lines with morphology
kernel = np.ones((3, 3), np.uint8)
close = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
open = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
thresh_blur = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

strategies = [
    ("close", close),
    ("open", open),
    ("blur+otsu", thresh_blur),
    ("bottom half", gray[h//2:, :]),
    ("bottom half upscale", cv2.resize(gray[h//2:, :], (w*2, h))), # stretch vertically
]

for name, processed in strategies:
    decoded = pyzbar_decode(Image.fromarray(processed))
    if decoded:
        print(f"✅ Found with strategy: {name}")
        for code in decoded:
            print(f"   Type: {code.type}, Data: {code.data.decode('utf-8')}")
    else:
        print(f"❌ Failed: {name}")
