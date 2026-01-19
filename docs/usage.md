# Usage

This repo provides two entry points:

- Debug harness: `python debug\debug.py`
- Simple scripts: `python script.py` (run from your project folder). Example:

```powershell
Set-Location scripts\momotalk
python script.py
```

## Setup

1. Install Python 3.11.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Config

Runtime looks for `config.json` in the current folder first. If missing, it falls back to the repo root `config.json`.

Key fields used by the runtime:
- `target.window_title_substring`
- `target.process_name`
- `reference_resolution`
- `render_area.mode` (`stretch`, `fit`, `manual`)
- `marker_detection.method` (`template`, `feature`, `pixel`)
- `marker_detection.threshold`
- `marker_detection.min_score_delta`
- `input.mouse_motion` (`instant`, `linear`, `ease`, `human`)
- `input.mouse_motion_duration_ms` (non-zero enables motion profiles)
- `input.mouse_motion_fps` (default 60)
- `input.mouse_jitter_px` (only used for `human`)
- `debug.log` (logs runtime actions)
- `debug.screenshot` (saves pixel verification screenshots to `debug_out` when enabled)

Notes:
- For `marker_detection.method = "feature"`, the score is a ratio of matched keypoints (0.0–1.0). Thresholds like `0.05–0.30` are common.

## Script basics

Typical flow:

```python
from engine.runtime import action, wait_for

action("marker1.png")
wait_for("statecheck.png")
action("marker2.png")
```

Branching:

```python
from engine.runtime import action, wait_for_absent, wait_for_image_optional, press_until_optional

if wait_for_image_optional("statecheck.png", timeout_s=10.0):
    action("marker2.png")
else:
    action("fallback.png")
```

Wait for a screen to disappear:

```python
from engine.runtime import wait_for_absent

wait_for_absent("anchor.png", timeout_s=10.0)
```

Optional spam until a state appears:

```python
from engine.runtime import press_until_optional

if press_until_optional("statecheck.png", ["1", "space"], timeout_s=30.0, step_delay_s=0.5):
    action("marker_next.png")
```

Tight ROI with roi_ref:

```python
from engine.runtime import wait_for

wait_for("abc.png", roi_ref=(191, 146, 285, 91))
```

## Sleep and timing

Use `engine.runtime.sleep(seconds)` instead of `time.sleep`. It is interruptible by the stop hotkey, so you can regain control immediately.

## Hotkeys

In scripts:
- `hotkey_stop("F10")`: stop the current run (goes to standby).
- `hotkey_restart("F5")`: restart from standby.

In debug harness (defaults, configurable in config.json):
- `Ctrl+F5`: log mouse position once.
- `Ctrl+Shift+F5`: toggle mouse tracking.
