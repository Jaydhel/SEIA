"""
Mouse Tracking Tool
Standalone mouse tracking hotkey (based on debug.py).
Press F8 to toggle tracking.
"""
from __future__ import annotations

import ctypes
import os
import sys
import logging
import time
from ctypes import wintypes
from typing import Any, Dict, Tuple

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from engine.capture import ScreenCapture
from engine.mapper import find_window, get_client_origin_and_size, is_window_minimized, set_process_dpi_awareness
import keyboard
import json

CONFIG_PATH = os.path.join(PARENT_DIR, "config.json")
DEFAULT_TRACK_MOUSE_HOTKEY = "f8"
MOUSE_TRACK_INTERVAL_S = 0.2


def _get_cursor_pos() -> Tuple[int, int]:
    point = wintypes.POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return int(point.x), int(point.y)
    return 0, 0


def _get_ref_size(config: Dict[str, Any]) -> Tuple[int, int]:
    ref = config.get("reference_resolution", {})
    return int(ref.get("w", 1920)), int(ref.get("h", 1080))


def _compute_render_rect(
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


def main():
    """Main entry point for mouse tracking tool."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    set_process_dpi_awareness()

    if not os.path.exists(CONFIG_PATH):
        logging.error("Config file not found: %s", CONFIG_PATH)
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    target_cfg = config.get("target", {})
    window_title = target_cfg.get("window_title_substring", "")
    process_name = target_cfg.get("process_name", "") or None

    hwnd = find_window(window_title, process_name)
    if not hwnd:
        logging.error("Could not find window with title containing: %s", window_title)
        return

    ref_size = _get_ref_size(config)
    render_cfg = config.get("render_area", {})

    capture = ScreenCapture()
    mouse_state = {
        "track": True,
        "last_report": 0.0
    }

    def toggle_tracking():
        mouse_state["track"] = not mouse_state["track"]
        status = "ON" if mouse_state["track"] else "OFF"
        mouse_state["last_report"] = 0.0
        logging.info("Mouse tracking %s", status)

    keyboard.add_hotkey(DEFAULT_TRACK_MOUSE_HOTKEY, toggle_tracking)

    def log_mouse_position():
        x, y = _get_cursor_pos()
        if is_window_minimized(hwnd):
            logging.warning("Window is minimized; mouse log skipped.")
            return
        try:
            origin_x, origin_y, client_w, client_h = get_client_origin_and_size(hwnd)
        except Exception as exc:
            logging.error("Failed to read window metrics: %s", exc)
            return
        render_x, render_y, render_w, render_h = _compute_render_rect(
            (origin_x, origin_y), (client_w, client_h), ref_size, render_cfg
        )
        scale_x = render_w / ref_size[0] if ref_size[0] else 1.0
        scale_y = render_h / ref_size[1] if ref_size[1] else 1.0
        ref_x = int(round((x - render_x) / scale_x)) if scale_x else 0
        ref_y = int(round((y - render_y) / scale_y)) if scale_y else 0

        try:
            pixel_img = capture.grab((x, y, 1, 1))
            if pixel_img is not None and pixel_img.size > 0:
                b, g, r = pixel_img[0, 0]
                rgb = (int(r), int(g), int(b))
                hex_color = f"#{r:02X}{g:02X}{b:02X}"
                
                # ANSI color escape for terminal visualization
                ansi_bg = f"\033[48;2;{r};{g};{b}m"
                ansi_reset = "\033[0m"
                color_block = f"{ansi_bg}    {ansi_reset}"
                
                logging.info(
                    "Mouse screen %d,%d -> ref %d,%d | RGB%s %s %s (render origin %d,%d, scale %.3f/%.3f)",
                    x,
                    y,
                    ref_x,
                    ref_y,
                    rgb,
                    hex_color,
                    color_block,
                    render_x,
                    render_y,
                    scale_x,
                    scale_y,
                )
            else:
                logging.info(
                    "Mouse screen %d,%d -> ref %d,%d (render origin %d,%d, scale %.3f/%.3f)",
                    x,
                    y,
                    ref_x,
                    ref_y,
                    render_x,
                    render_y,
                    scale_x,
                    scale_y,
                )
        except Exception:
            logging.info(
                "Mouse screen %d,%d -> ref %d,%d (render origin %d,%d, scale %.3f/%.3f)",
                x,
                y,
                ref_x,
                ref_y,
                render_x,
                render_y,
                scale_x,
                scale_y,
            )

    try:
        logging.info("Mouse tracking tool ready.")
        logging.info("Hotkey: %s toggle tracking", DEFAULT_TRACK_MOUSE_HOTKEY)
        logging.info("Tracking starts ON.")
        logging.info("Press Ctrl+C to exit.")
        while True:
            if mouse_state["track"]:
                now = time.monotonic()
                if now - mouse_state["last_report"] >= MOUSE_TRACK_INTERVAL_S:
                    log_mouse_position()
                    mouse_state["last_report"] = now
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        logging.info("Exiting...")
    finally:
        keyboard.unhook_all_hotkeys()


if __name__ == "__main__":
    main()
