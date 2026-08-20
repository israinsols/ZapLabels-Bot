import barcode
from barcode.writer import ImageWriter
import io

data = "1ZA668990495524105"

try:
    # Try user's way
    code128 = barcode.get('code128', '')
    rv = io.BytesIO()
    code128(data, writer=ImageWriter()).write(rv)
    print("User's way worked!")
except Exception as e:
    print(f"User's way failed: {type(e).__name__}: {e}")

try:
    # Try correct way
    code128_class = barcode.get_barcode_class('code128')
    my_barcode = code128_class(data, writer=ImageWriter())
    rv = io.BytesIO()
    my_barcode.write(rv)
    print("Correct way 1 worked!")
except Exception as e:
    print(f"Correct way 1 failed: {type(e).__name__}: {e}")

try:
    # Try another correct way
    my_barcode = barcode.get('code128', data, writer=ImageWriter())
    rv = io.BytesIO()
    my_barcode.write(rv)
    print("Correct way 2 worked!")
except Exception as e:
    print(f"Correct way 2 failed: {type(e).__name__}: {e}")
