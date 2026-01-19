from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

import cv2

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from engine.capture import ScreenCapture
from engine.mapper import find_window, get_client_origin_and_size, set_process_dpi_awareness


ROOT_DIR = PARENT_DIR
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_ref_size(config: Dict[str, Any]) -> Tuple[int, int]:
    ref = config.get("reference_resolution", {})
    return int(ref.get("w", 1920)), int(ref.get("h", 1080))


def compute_render_rect(
    client_origin: Tuple[int, int],
    client_size: Tuple[int, int],
    ref_size: Tuple[int, int],
    render_cfg: Dict[str, Any],
) -> Tuple[int, int, int, int]:
    mode = str(render_cfg.get("mode", "stretch")).lower()
    client_w, client_h = client_size
    ref_w, ref_h = ref_size
    if mode == "manual":
        offset = render_cfg.get("offset", {})
        size = render_cfg.get("size", {})
        width = int(size.get("w", 0)) or client_w
        height = int(size.get("h", 0)) or client_h
        off_x = int(offset.get("x", 0))
        off_y = int(offset.get("y", 0))
        return client_origin[0] + off_x, client_origin[1] + off_y, width, height
    if mode == "fit":
        if ref_w <= 0 or ref_h <= 0 or client_w <= 0 or client_h <= 0:
            return client_origin[0], client_origin[1], client_w, client_h
        scale = min(client_w / ref_w, client_h / ref_h)
        render_w = int(round(ref_w * scale))
        render_h = int(round(ref_h * scale))
        off_x = int(round((client_w - render_w) / 2))
        off_y = int(round((client_h - render_h) / 2))
        return client_origin[0] + off_x, client_origin[1] + off_y, render_w, render_h
    return client_origin[0], client_origin[1], client_w, client_h


def main() -> None:
    set_process_dpi_awareness()
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Missing config: {CONFIG_PATH}")
    config = load_config(CONFIG_PATH)
    target = config.get("target", {})
    title_substring = target.get("window_title_substring", "")
    process_name = target.get("process_name", "") or None
    hwnd = find_window(title_substring, process_name)
    if hwnd is None:
        raise RuntimeError("Target window not found.")

    ref_size = get_ref_size(config)
    render_cfg = config.get("render_area", {})

    origin_x, origin_y, client_w, client_h = get_client_origin_and_size(hwnd)
    render_x, render_y, render_w, render_h = compute_render_rect(
        (origin_x, origin_y), (client_w, client_h), ref_size, render_cfg
    )

    capture = ScreenCapture()
    img = capture.grab((render_x, render_y, render_w, render_h))
    if img is None:
        raise RuntimeError("Capture failed.")

    scale_x = render_w / ref_size[0] if ref_size[0] else 1.0
    scale_y = render_h / ref_size[1] if ref_size[1] else 1.0

    window_name = "ROI Picker (drag to select, press q to quit)"
    selecting = {"start": None, "end": None, "rect": None}

    def on_mouse(event, x, y, _flags, _param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            selecting["start"] = (x, y)
            selecting["end"] = (x, y)
            selecting["rect"] = None
        elif event == cv2.EVENT_MOUSEMOVE and selecting["start"] is not None:
            selecting["end"] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and selecting["start"] is not None:
            selecting["end"] = (x, y)
            x0, y0 = selecting["start"]
            x1, y1 = selecting["end"]
            left = min(x0, x1)
            top = min(y0, y1)
            width = abs(x1 - x0)
            height = abs(y1 - y0)
            selecting["rect"] = (left, top, width, height)
            selecting["start"] = None

            ref_x = int(round(left / scale_x)) if scale_x else 0
            ref_y = int(round(top / scale_y)) if scale_y else 0
            ref_w = int(round(width / scale_x)) if scale_x else 0
            ref_h = int(round(height / scale_y)) if scale_y else 0
            print(
                f"ROI ref: {{\"x\": {ref_x}, \"y\": {ref_y}, \"w\": {ref_w}, \"h\": {ref_h}}}"
            )

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse)

    while True:
        frame = img.copy()
        if selecting["start"] is not None and selecting["end"] is not None:
            x0, y0 = selecting["start"]
            x1, y1 = selecting["end"]
            cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 255, 0), 2)
        elif selecting["rect"] is not None:
            left, top, width, height = selecting["rect"]
            cv2.rectangle(frame, (left, top), (left + width, top + height), (0, 255, 0), 2)
        cv2.imshow(window_name, frame)
        if cv2.waitKey(20) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
