import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from PIL import Image

image_path = r"C:\Users\ccslaptophyd\.gemini\antigravity\brain\bef353d3-a1e2-4528-bbbf-34b58af8dfd3\.user_uploaded\uploaded_media_1786802256206.png"

img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
h, w = gray.shape

strategies = [
    ("raw gray", gray),
    ("threshold", cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY)[1]),
    ("adaptive", cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)),
    ("Otsu", cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]),
    ("2x upscale", cv2.resize(gray, (w*2, h*2), interpolation=cv2.INTER_CUBIC)),
    ("3x upscale", cv2.resize(gray, (w*3, h*3), interpolation=cv2.INTER_CUBIC)),
    ("sharpened", cv2.filter2D(gray, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))),
]

for name, processed in strategies:
    decoded = pyzbar_decode(Image.fromarray(processed))
    if decoded:
        print(f"✅ Found with strategy: {name}")
        for code in decoded:
            print(f"   Type: {code.type}, Data: {code.data.decode('utf-8')}")
    else:
        print(f"❌ Failed: {name}")
