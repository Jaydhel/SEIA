# Add Pixel Verification (Quick Guide)

Pixel verification helps avoid false positives by checking a few exact pixels
after a template match. Use it when a template matches on the wrong screen.

## Step 1: Find a distinctive pixel
1. Run the debug tool: `python debug\debug.py`
2. Press `Ctrl+Shift+F5` to enable mouse tracking.
3. Hover a distinctive colored pixel on the correct UI.
4. Note the RGB values from the console.

## Step 2: Get the template offsets (recommended)
Use the pixel picker to get the template-relative offsets:

```bash
python debug\pick_pixels.py templates\statecheck2.png
```

Click the same pixel you saw on screen. The tool prints `(x, y, (r, g, b), tolerance)`.

## Step 3: Add `verify_pixels` to your call

```python
press_until(
    "statecheck2.png",
    ["1", "space"],
    30.0,
    near=STATECHECK2_NEAR,
    radius=STATECHECK2_RADIUS,
    verify_pixels=[
        (9, 0, (244, 245, 246), 30),
    ],
)
```

You can use `verify_pixels` with `action`, `wait_for`, and `press_until`.

## Notes

- Offsets are relative to the template top-left.
- Use 2-3 pixels for better reliability.
- Tolerance `20-40` is usually a good starting range.
