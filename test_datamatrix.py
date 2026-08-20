from datamatrix_processor import DataMatrixProcessor

# Test with your Royal Mail label
image_path = "royalmail_label.png"  # Apni label ki path daalo

result = DataMatrixProcessor.process_label(image_path)

if result:
    print("\n📋 Final Result:")
    print(f"   Payload: {result['payload']}")
    print(f"   Fields: {result['fields']}")
    print(f"   Structure: {result['structure']}")
    print(f"   BBox: {result['bbox']}")