# Detector Harness (Windows, Python 3.11)

This project is a safe, windowed "detector harness" for validating coordinate mapping and on-screen detection before building any automation bot. It only uses screen capture + computer vision + optional one-shot input for calibration.

## Setup

1. Install Python 3.11.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the debug harness:

```bash
python debug\debug.py
```

On first launch, `config.json` and `templates/` are created if missing.

## Hotkeys

- `F8`: Toggle monitoring on/off.
- `Ctrl+F10`: Exit.
- `Ctrl+F4`: Reload `config.json` and the template (no restart needed).
- `Ctrl+F6`: One-shot test click (only if `test_input.enabled` is true).
- `Ctrl+F7`: One-shot ESC keypress (only if `test_input.enabled` is true).
- `Ctrl+F2`: One-shot scroll down (amount set by `test_input.scroll_amount`).
- `Ctrl+F1`: Set marker near/radius (prompt in console, ref coords).
- `Ctrl+F9`: One-shot click on the best template match inside `marker_roi` (template mode only).
- `Ctrl+F11`: One-shot click at the current mouse cursor position.
- `Ctrl+F5`: Log current mouse position in screen + reference coords (helps you set ROIs).
- `Ctrl+F3`: Set marker click offset (prompt in console, ref coords).

## CLI keys (console)

When the debug harness console is focused, you can also use:

- `A`: Toggle monitoring.
- `B`: Toggle threshold bypass (ignore configured marker threshold).
- `C`: Reload config/template.
- `H`: Print the CLI help line again.

## Automation engine (scripting)

The automation engine is a lightweight library for writing your own scripts. It uses the same `config.json` for window targeting, DPI mapping, and render area.

Example (simple script):

```python
from engine import AutomationEngine

engine = AutomationEngine()
engine.action("templates/marker.png", coords_offset=(0, 0), click_duration=0.0, timeout_s=10.0)
```

Key functions:

- `action(image_path, coords_offset, click_duration, timeout_s, roi_ref, threshold) -> bool`
  - Waits until the image is found, then clicks once.
  - `coords_offset` is in reference pixels by default (1920x1080 space).
  - `click_duration` holds the click for N seconds (0.0 = normal click).
- `use_default_threshold=False` bypasses the configured default threshold and matches any score (use with care).
- `image_present(image_path, roi_ref, threshold) -> bool`
  - Checks once, returns True/False.
- `wait_for_image(image_path, roi_ref, threshold, timeout_s) -> MatchResult | None`
  - Waits up to `timeout_s` and returns match info.
- `move_to_ref(x, y, duration=0.0) -> None`
  - Moves the mouse to a 1920x1080 reference coordinate.
- `move_to_screen(x, y, duration=0.0) -> None`
  - Moves the mouse to an absolute screen coordinate.

You can write custom Python scripts around these calls for sequential logic.

For a minimal, end-user-friendly script, see `momotalk/script.py` which uses `engine/runtime.py` helpers.

Runtime helper functions (engine/runtime.py)

These helpers are intended for simple scripts. All coordinates are 1920x1080 reference coords unless noted.

Functions:
- `action(image_name, coords_offset=(0,0), click_duration=0.0, timeout_s=..., use_default_threshold=True, require=True, near=None, radius=None) -> bool`
  - Waits for an image and clicks its center (plus optional offset). Returns True on success, exits on timeout if `require=True`.
- `press(key) -> None`
  - Sends a single keypress.
- `press_until(image_name, keys, timeout_s=..., step_delay_s=..., use_default_threshold=True, require=True, near=None, radius=None, roi_ref=None) -> bool`
  - Repeats key presses until the image appears.
- `press_until_optional(image_name, keys, timeout_s=..., step_delay_s=..., use_default_threshold=True, near=None, radius=None, roi_ref=None) -> bool`
  - Same as `press_until`, but never exits on timeout (returns True/False).
- `wait_for(image_name, timeout_s=..., step_delay_s=..., use_default_threshold=True, require=True, near=None, radius=None, roi_ref=None) -> bool`
  - Waits for an image. Exits on timeout if `require=True`.
- `wait_for_image_optional(image_name, timeout_s=..., step_delay_s=..., use_default_threshold=True, near=None, radius=None, roi_ref=None) -> bool`
  - Waits for an image and returns True/False without exiting (useful for branching).
- `wait_for_absent(image_name, timeout_s=..., step_delay_s=..., use_default_threshold=True, require=True, near=None, radius=None, roi_ref=None) -> bool`
  - Waits for an image to disappear. Exits on timeout if `require=True`.
- `wait_for_absent_optional(image_name, timeout_s=..., step_delay_s=..., use_default_threshold=True, near=None, radius=None, roi_ref=None) -> bool`
  - Waits for an image to disappear and returns True/False without exiting.
- `present(image_name, use_default_threshold=True, near=None, radius=None) -> bool`
  - Checks once and returns True/False.
- `hotkey_stop(key="F10") -> None`
  - Stop the current run (raises SystemExit).
- `hotkey_restart(key="F5") -> None`, `wait_for_restart() -> None`
  - Puts the script in standby and waits for a restart hotkey.
- `reset_stop() -> None`, `cleanup() -> None`, `sleep(seconds) -> None`
  - Utility helpers for run control.
- `set_marker_dir(path) -> None`
  - Adds a marker search path.

Examples:

Wait for a confirmation screen and branch:
```python
from engine.runtime import action, wait_for_image_optional

if wait_for_image_optional("statecheck.png", timeout_s=10.0):
    action("marker2.png")
else:
    action("fallback.png")
```

Click a marker within a small region:
```python
from engine.runtime import action

action("marker1.png", near=(270, 226), radius=90)
```

Runtime debug logging: set `debug.log` to `true` in the active `config.json` to print each `engine/runtime.py` action (action/press/press_until) to the CLI.

## ROI picker tool

Run `python debug\roi_picker.py`, drag a box over the window, and it prints a JSON ROI in 1920x1080 reference coords.

## ROI (Region of Interest)

ROI stands for "Region of Interest" — a rectangular area of the screen to search instead of scanning the whole window. It makes detection faster and avoids false matches when similar UI appears in multiple places.

In `engine/runtime.py`, you can pass `near=(x,y)` and `radius=N` (reference coords) to search only near that spot.

## Calibration (step-by-step)

1. Run the harness and press `F8` to start monitoring.
2. Move the game window around and confirm the ROIs stay aligned.
3. Use `F6` on a known UI element to validate coordinate mapping.
4. Tune `marker_roi` and `marker_detection.threshold` (or pixel points) until marker detection is stable.
5. Tune `change_roi` and `screen_change_detection.delta_threshold` until changes are detected reliably.
6. Enable `debug.save_frames` and `debug.overlay` to confirm crops/overlays in `debug_out`.

## Render area (why 1920x1080 still works)

Your reference coordinates are always 1920x1080, but many windowed games render smaller and letterbox inside the client area. The `render_area` setting tells the harness which part of the client is the actual rendered game:

- `mode: "fit"` (default): assumes the game keeps 16:9 aspect and is centered. The harness computes the largest 16:9 area that fits inside the client. This is correct for most games that letterbox.
- `mode: "stretch"`: uses the full client area as the render area (no letterbox). Use this if the game stretches to the window size.
- `mode: "manual"`: explicitly set the render area inside the client. Use this if the game has fixed margins or odd offsets.

Manual example (top-left offset 20,30 and a 1738x978 render):

```json
"render_area": {
  "mode": "manual",
  "offset": { "x": 20, "y": 30 },
  "size": { "w": 1738, "h": 978 }
}
```

The status line prints `Scale` and (when applicable) `Render WxH` so you can confirm the computed area.

## How it works

- The window is located by title substring (and optional process name).
- The client area top-left is computed with `ClientToScreen`.
- All coordinates are mapped from a 1920x1080 reference space to screen space at runtime.
- Each poll:
  - `marker_roi` is captured and evaluated with template match or pixel checks.
  - `change_roi` is captured and evaluated against a baseline using ROI delta.
- The client origin is re-read every loop to handle window movement.

## Config highlights

- `reference_resolution`: The 1920x1080 reference coordinate space.
- `render_area`: Controls how the render area is derived inside the client (`fit`, `stretch`, or `manual`). Use `stretch` if the game fills the client with no letterbox margins.
- `rois.marker_roi` and `rois.change_roi`: Rectangles in reference coords.
- `marker_detection.method`: `template`, `feature`, or `pixel`.
- `marker_detection.min_score_delta`: Requires the best match to be clearly above the next best match (reduces false positives).
- `marker_detection.bypass_threshold`: If true, ignore the configured threshold (use only for debugging).
- `screen_change_detection.delta_threshold`: Mean abs diff threshold.
- `debug.save_frames`: Dumps annotated frames to `debug_out`.
- `debug.screenshot`: Saves pixel verification screenshots (`verify_pass_*.png`/`verify_fail_*.png`) to `debug_out` when `marker_detection.use_pixel_verification` is enabled.

## Troubleshooting

- **DPI scaling mismatch**: Ensure Windows scaling is consistent. The app sets DPI awareness, but unusual per-monitor scaling can still affect mapping.
- **Fullscreen capture**: This harness targets windowed mode only. Fullscreen capture is out of scope.
- **Template not found**: Place the template at `templates/marker.png` or update `config.json`.
- **Window not found**: Check `target.window_title_substring` and optional `process_name`.
- **pywin32 import errors**: Ensure the `pywin32` wheel matches your Python version/architecture (reinstall in the active env). The harness falls back to ctypes if pywin32 fails.
- **Non-1080p render size**: Keep reference coords at 1920x1080, set `render_area.mode` to `fit` or `manual`, and the template matcher will auto-scale.

## Notes

- No memory reading, injection, hooks, or evasion.
- Input is only sent when explicitly triggered via hotkeys.
