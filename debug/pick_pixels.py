"""
Pixel Color Picker Tool
Helps you find good verification pixels for your template images.
"""
import os
import cv2
import sys

def pick_pixels(image_path):
    """Interactive tool to pick verification pixels from an image."""
    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        return
    
    # Convert to BGR if it has alpha channel
    if img.ndim == 3 and img.shape[2] == 4:
        img_bgr = img[:, :, :3].copy()  # Make writable copy
    else:
        img_bgr = img.copy()  # Make writable copy
    
    height, width = img_bgr.shape[:2]
    print(f"\nImage: {image_path}")
    print(f"Size: {width}x{height}")
    print("\nClick on distinctive colored pixels (avoid white/gray areas)")
    print("Press 'q' to quit and generate code\n")
    
    selected_pixels = []
    
    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if y < height and x < width:
                b, g, r = img_bgr[y, x]
                rgb = (int(r), int(g), int(b))
                print(f"  Pixel at ({x}, {y}): RGB{rgb}")
                selected_pixels.append((x, y, rgb))
                # Draw marker on a copy that we know is writable
                display_img = img_bgr.copy()
                cv2.circle(display_img, (x, y), 3, (0, 255, 0), -1)
                cv2.imshow('Pick Pixels', display_img)
    
    cv2.namedWindow('Pick Pixels')
    cv2.setMouseCallback('Pick Pixels', mouse_callback)
    cv2.imshow('Pick Pixels', img_bgr)
    
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    if selected_pixels:
        print("\n" + "="*60)
        print("Add this to your script:")
        print("="*60)
        filename = image_path.split("/")[-1].split("\\")[-1]
        
        # Output new simplified syntax
        print(f'wait_for("{filename}", verify_pixels=[')
        for x, y, rgb in selected_pixels:
            print(f'    ({x}, {y}, {rgb}, 30),')
        print('])')
        
        print("\n" + "="*60)
        print("OR for action/press_until:")
        print("="*60)
        print(f'action("{filename}", verify_pixels=[')
        for x, y, rgb in selected_pixels:
            print(f'    ({x}, {y}, {rgb}, 30),')
        print('])')
        
        print("\n" + "="*60)
        print("OLD SYNTAX (still works):")
        print("="*60)
        print(f'add_pixel_verification("{filename}", [')
        for x, y, rgb in selected_pixels:
            print(f'    ({x}, {y}, {rgb}, 30),')
        print('])')
        print("="*60)
    else:
        print("\nNo pixels selected!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pick_pixels(sys.argv[1])
    else:
        # Default to statecheck4.png
        default_path = os.path.join(os.getcwd(), "templates", "marker.png")
        pick_pixels(default_path)
