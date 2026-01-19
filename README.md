# Seia (State Evaluated Image Automation)

![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-27338e?style=for-the-badge&logo=opencv&logoColor=white)

Seia is a Windows screen automation harness for games and desktop apps. It uses
screen capture, template matching, and optional pixel verification to help you
build simple scripts without memory access, injection, or hooks.

## Features

- Windowed capture with stable coordinate mapping (1920x1080 reference space).
- Template matching, feature matching, and pixel verification.
- ROI helpers for faster, safer detection.
- Debug harness with hotkeys for calibration and testing.
- Lightweight runtime helpers for basic scripting.

## Non-goals

- No memory reading, injection, or evasion.
- No fullscreen capture (windowed only).

## Requirements

- Windows 10+
- Python 3.11

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick start

1. Run the debug harness:

```bash
python debug\debug.py
```

2. Update `config.json` to target your app window and templates.
3. Run your script (example):

```bash
Set-Location scripts\momotalk
python script.py
```

## Configuration

Runtime config resolution order:
1. `./config.json` (current working directory)
2. Repo root `config.json`

You can override with an environment variable:

```powershell
$env:SEIA_CONFIG_PATH = "C:\path\to\config.json"
```

Key settings (full list in `docs/usage.md`):
- `target.window_title_substring`
- `target.process_name`
- `marker_detection.method`
- `marker_detection.threshold`
- `marker_detection.min_score_delta`
- `input.mouse_motion`
- `debug.log` and `debug.screenshot`

### Custom folders (profiles)

You can create your own folder anywhere and point Seia at its `config.json`.
This lets you keep per-app assets (templates, scripts) together.

Example layout:

```
profiles/my-app/
  config.json
  templates/
  script.py
```

Option 1: Run from the profile folder (auto-uses `./config.json` and `./templates`):

```powershell
Set-Location profiles\my-app
python script.py
```

Option 2: Run from the repo root and override the config path:

```powershell
$env:SEIA_CONFIG_PATH = "$PWD\profiles\my-app\config.json"
python profiles\my-app\script.py
```

If your templates live outside the current working directory, call
`set_template_dir("C:\path\to\templates")` at the top of your script.

## Scripting

The simple API lives in `engine/runtime.py`:

```python
from engine.runtime import action, wait_for

action("marker1.png")
wait_for("statecheck.png", timeout_s=10.0)
```

For lower-level control, use `engine/core.py`.

## Tools

- ROI picker: `python debug\roi_picker.py`
- Debug harness hotkeys are printed in the console on startup.

## Docs

- `docs/usage.md` for setup and config details.
- `docs/PIXEL_VERIFICATION.md` for pixel verification workflow.

## Project layout

- `engine/` core capture, mapping, and detection.
- `debug/` debug harness and helper tools.
- `scripts/` example scripts (e.g., `scripts/momotalk/`).
- `templates/` default template location.
- `docs/` usage and verification guides.

## Contributing

PRs are welcome. Keep changes Windows-focused and avoid non-ASCII unless needed.

## License

Not specified yet.
