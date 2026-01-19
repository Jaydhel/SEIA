# EASY WAY TO ADD PIXEL VERIFICATION

## Your Original Code:
```python
press_until("statecheck2.png", ["1", "space"], 30.0, near=STATECHECK2_NEAR, radius=STATECHECK2_RADIUS)
```

## Step 1: Find the pixel to verify
1. Run debug tool: `python debug\debug.py`
2. Press `Ctrl+Shift+F5` to enable mouse tracking
3. Hover over a distinctive colored pixel in statecheck2 area
4. Note the RGB values (e.g., RGB(244, 245, 246))

## Step 2: Find the offset within the template
Since you need the offset from the TEMPLATE's top-left (not from screen position):

**Option A: Use the pixel picker tool (EASIEST)**
```bash
python momotalk\pick_pixels.py momotalk\marker\statecheck2.png
```
- Click on the same colored pixel you saw on screen
- It will show: `(x, y, (244, 245, 246), 25)`
- Use those exact values!

**Option B: Estimate manually**
If your template is around the center of the ROI:
- Template probably matches near (1707, 67)
- Mouse is at (1666, 67) 
- If template is 100px wide and centered at (1707, 67), it spans roughly (1657, 67) to (1757, 67)
- Your pixel at (1666, 67) is about 9 pixels from the left edge
- So offset would be approximately (9, 0) from template top-left

## Step 3: Add verify_pixels to your code

```python
press_until(
    "statecheck2.png", 
    ["1", "space"], 
    30.0, 
    near=STATECHECK2_NEAR, 
    radius=STATECHECK2_RADIUS,
    verify_pixels=[
        (9, 0, (244, 245, 246), 30),  # Adjust X offset after using picker tool
    ]
)
```

## RECOMMENDED: Just use the picker tool!
It's much more accurate than calculating manually:

```bash
cd C:\Users\Lychwee\Documents\GitHub\ba-helper
python momotalk\pick_pixels.py momotalk\marker\statecheck2.png
```

Click the pixel you want, get exact values, paste into code. Done! ✅
