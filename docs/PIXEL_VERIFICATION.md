# Pixel Verification System Documentation

## Overview

The **Pixel Verification System** is a two-stage image detection mechanism that eliminates false positives in template matching by verifying actual pixel colors at specific locations within a matched region.

## Problem It Solves

Traditional template matching can produce false positives when:
- Multiple similar-looking UI elements exist on different screens
- Images score identically (e.g., both 0.989 or 99%)
- Delta between best and second-best match is negligible (< 0.001)
- Visual similarity fools pixel-by-pixel comparison

**Example Issue:**
```
Correct screen:  Template match score = 0.989 at position (1570, 1042)
Wrong screen:    Template match score = 0.989 at position (1571, 1042)
```
Both are accepted! ❌

## How It Works

### Two-Stage Detection Process

```
┌─────────────────────────────────┐
│   Stage 1: Template Matching    │
│  (Fast, broad matching)         │
└─────────────┬───────────────────┘
              │
              ▼
      ┌──────────────┐
      │ Match Found? │
      └──────┬───────┘
             │ Yes
             ▼
┌─────────────────────────────────┐
│  Stage 2: Pixel Verification    │
│  (Precise color validation)     │
└─────────────┬───────────────────┘
              │
              ▼
      ┌──────────────────┐
      │ Pixels Match?    │
      └──────┬───────────┘
             │ Yes
             ▼
        ✅ ACCEPT
```

### Stage 1: Template Matching
- Uses OpenCV's `matchTemplate()` with normalized cross-correlation
- Finds potential match locations based on visual similarity
- Returns score (0.0 to 1.0) and position (x, y)

### Stage 2: Pixel Verification
- Checks **actual RGB values** at specific pixel coordinates
- Coordinates are **relative to the matched template's top-left corner**
- Only accepts match if **all** verification pixels match expected colors
- Uses tolerance to account for compression artifacts

## Implementation Details

### 1. Define Verification Points

```python
add_pixel_verification("logo.png", [
    # (x_offset, y_offset, (R, G, B), tolerance)
    (50, 20, (80, 80, 80), 30),      # Point 1: Dark gray pixel
    (100, 35, (255, 100, 50), 25),   # Point 2: Orange pixel
    (150, 10, (30, 100, 200), 20),   # Point 3: Blue pixel
])
```

**Parameters:**
- `x_offset`, `y_offset`: Position relative to template's **top-left corner**
- `(R, G, B)`: Expected RGB color values (0-255 each)
- `tolerance`: Allowed deviation per channel (typically 20-30)

### 2. Verification Process

When template matching finds a match at position (px, py):

```python
# For each verification point:
for (x_offset, y_offset, expected_rgb, tolerance) in verification_points:
    # Calculate absolute screen position
    abs_x = match_x + x_offset
    abs_y = match_y + y_offset
    
    # Sample actual pixel color
    actual_rgb = screenshot[abs_y, abs_x]
    
    # Check if within tolerance
    if not colors_match(actual_rgb, expected_rgb, tolerance):
        REJECT_MATCH()  # ❌ Pixel mismatch
        return False
    
# All pixels matched
ACCEPT_MATCH()  # ✅ Verified
return True
```

### 3. Color Matching Algorithm

```python
def colors_match(actual_rgb, expected_rgb, tolerance):
    """Check if RGB colors match within tolerance."""
    r_match = abs(actual_rgb[0] - expected_rgb[0]) <= tolerance
    g_match = abs(actual_rgb[1] - expected_rgb[1]) <= tolerance
    b_match = abs(actual_rgb[2] - expected_rgb[2]) <= tolerance
    
    return r_match and g_match and b_match
```

**Example:**
```
Expected: RGB(80, 80, 80) ± 30
Actual:   RGB(85, 75, 82)

R: |85 - 80| = 5  ≤ 30 ✓
G: |75 - 80| = 5  ≤ 30 ✓
B: |82 - 80| = 2  ≤ 30 ✓

Result: MATCH ✅
```

## Real-World Example

### Scenario
You have a logo that appears on both:
- **Correct UI**: At position (1570, 1042)
- **Wrong UI**: At position (1571, 1042) (1 pixel away!)

Both score 0.989 in template matching.

### Solution

**Step 1: Find Distinctive Pixel**

Run the pixel picker tool:
```bash
python pick_pixels.py
```

Click on a colored pixel in your logo (avoid white/gray/black).

**Step 2: Note Color Difference**

```
Correct UI - Pixel at offset (50, 20): RGB(80, 80, 80)   - Dark gray
Wrong UI   - Pixel at offset (50, 20): RGB(242, 242, 244) - Light gray
```

**Step 3: Add Verification**

```python
add_pixel_verification("statecheck4.png", [
    (50, 20, (80, 80, 80), 30),  # Dark gray - correct UI only
])
```

**Step 4: Results**

```
Correct UI:
  Template match: 0.989 ✓
  Pixel check: RGB(80,80,80) matches RGB(80,80,80) ± 30 ✓
  → ACCEPTED ✅

Wrong UI:
  Template match: 0.989 ✓
  Pixel check: RGB(242,242,244) vs RGB(80,80,80) ± 30 ✗
  → REJECTED ❌
```

## Configuration

Enable in `config.json`:

```json
{
  "marker_detection": {
    "method": "template",
    "threshold": 0.95,
    "use_pixel_verification": true
  }
}
```

## Choosing Good Verification Pixels

### ✅ Good Pixels
- **Unique colors** (blues, reds, oranges, purples)
- **Mid-range brightness** (avoid pure white/black)
- **Stable areas** (not near gradients or anti-aliased edges)
- **Multiple pixels** (2-3 points for redundancy)

### ❌ Bad Pixels
- White (255, 255, 255) - too common
- Black (0, 0, 0) - too common
- Gray (128, 128, 128) - ambiguous
- Edge pixels - affected by compression artifacts
- Single pixel only - not robust

## Best Practices

### 1. Use 2-3 Verification Points
```python
add_pixel_verification("logo.png", [
    (30, 15, (50, 100, 200), 25),   # Top-left distinctive color
    (108, 24, (200, 50, 100), 25),  # Center distinctive color
    (180, 40, (100, 200, 50), 25),  # Bottom-right distinctive color
])
```

**Why?** Multiple points ensure:
- Redundancy (if one pixel changes due to UI updates)
- Stronger verification (harder to fake all pixels)
- Better spatial coverage

### 2. Set Appropriate Tolerance

```python
# Too strict (may fail on compression)
tolerance = 5  # ❌

# Good balance
tolerance = 20-30  # ✅

# Too loose (may accept wrong colors)
tolerance = 100  # ❌
```

### 3. Pick Pixels from Stable UI Elements
- Logos, icons, text
- Avoid: animations, hover effects, dynamic content

### 4. Test Both Screens
Verify that:
- Correct screen: Pixels match ✅
- Wrong screen: Pixels don't match ❌

## Tools Provided

### Pixel Picker Tool (`pick_pixels.py`)

Interactive GUI tool to select verification pixels:

```bash
python pick_pixels.py [image_path]
```

**Usage:**
1. Opens image in window
2. Click on distinctive colored pixels (avoid white/gray)
3. Press 'q' when done
4. Outputs ready-to-use code:

```python
add_pixel_verification("statecheck4.png", [
    (50, 20, (80, 80, 80), 25),
    (100, 35, (255, 100, 50), 25),
])
```

## Performance Impact

- **Template Matching**: ~5-10ms per match
- **Pixel Verification**: ~0.1ms per pixel (negligible)
- **Total overhead**: < 1ms for 3 pixels

Pixel verification adds virtually no performance cost while dramatically improving accuracy.

## Troubleshooting

### Issue: Both Screens Rejected

**Cause:** Wrong expected RGB values

**Solution:**
1. Check debug logs for actual pixel colors:
   ```
   INFO:root:Pixel verification FAILED: expected RGB(255,100,50), got RGB(80,80,80)
   ```
2. Update expected values to match the **correct** screen's colors

### Issue: Wrong Screen Accepted

**Cause:** Pixels are too similar between screens

**Solution:**
1. Pick different verification pixels with more color contrast
2. Add more verification points (3-5 instead of 1-2)
3. Choose pixels from unique UI elements that don't exist on wrong screen

### Issue: Correct Screen Sometimes Rejected

**Cause:** Tolerance too strict or compression artifacts

**Solution:**
1. Increase tolerance from 20 to 30-40
2. Avoid edge pixels (use pixels 5-10px inside template)
3. Test with multiple screenshots to account for variations

## Architecture

### File Structure

```
engine/
├── verify.py          # Pixel verification system
├── core.py            # Integration with AutomationEngine
└── runtime.py         # User-facing API

debug/
└── pick_pixels.py     # Interactive pixel picker tool

your-app/
└── script.py          # User script with verification calls
```

### API Reference

#### `add_pixel_verification(image_name, points)`

Registers pixel verification points for an image.

**Parameters:**
- `image_name` (str): Template filename (e.g., "logo.png")
- `points` (List[Tuple]): List of verification points
  - Each point: `(x, y, (r, g, b), tolerance)`

**Example:**
```python
from engine.runtime import add_pixel_verification

add_pixel_verification("button.png", [
    (25, 10, (100, 150, 200), 25),
])
```

#### `verify_match(screenshot, match_location, image_name)`

Internal function that performs verification (called automatically).

**Returns:**
- `True`: All pixels match
- `False`: At least one pixel doesn't match

## When to Use Pixel Verification

### ✅ Use When:
- Template matching produces false positives
- Multiple screens have visually similar elements
- Score delta between matches is < 0.02
- You need conditional logic (if image exists, do X)

### ❌ Don't Use When:
- Template matching already works perfectly
- Image is unique enough (no false positives)
- Feature detection (ORB/SIFT) is available and works
- Performance is critical (though impact is minimal)

## Comparison with Alternative Methods

| Method | Speed | Accuracy | False Positives | Best For |
|--------|-------|----------|-----------------|----------|
| Template Only | Fast | Medium | High | Unique images |
| Feature (ORB) | Medium | High | Low | Complex images with keypoints |
| Template + Pixel Verification | Fast | Very High | Very Low | Simple/small images |
| Multi-template | Slow | High | Low | Stateful UI detection |

## Conclusion

Pixel verification provides a lightweight, highly accurate solution for eliminating false positives in template matching. By checking actual pixel colors at strategic locations, it distinguishes between visually similar images that would otherwise be indistinguishable.

**Key Benefits:**
- ✅ Eliminates false positives
- ✅ Negligible performance overhead
- ✅ Easy to configure with pixel picker tool
- ✅ Works with simple/small images where feature detection fails
- ✅ Robust against minor UI variations (with proper tolerance)

**Perfect for:**
- Game automation (UI state detection)
- Conditional workflows (if button exists, click it)
- Simple logos/icons that lack distinctive features
- Situations where ORB/SIFT find 0 keypoints
