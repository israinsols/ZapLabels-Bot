import cv2
import numpy as np
from pyzbar.pyzbar import decode as pyzbar_decode
from pylibdmtx.pylibdmtx import decode as dmtx_decode
from PIL import Image

image_path = r"C:\Users\ccslaptophyd\.gemini\antigravity\brain\bef353d3-a1e2-4528-bbbf-34b58af8dfd3\.user_uploaded\uploaded_media_1786802256206.png"
img = cv2.imread(image_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

print("Trying pyzbar...")
decoded = pyzbar_decode(Image.fromarray(gray))
for code in decoded:
    print(f"pyzbar: {code.type} - {code.data.decode('utf-8')}")

print("Trying pylibdmtx...")
dmtx_res = dmtx_decode(Image.fromarray(gray))
for code in dmtx_res:
    print(f"dmtx: Data Matrix - {code.data.decode('utf-8')}")

print("Done")
