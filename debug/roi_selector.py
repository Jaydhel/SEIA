"""
ROI Rectangle Selector Tool
Click two points on screen to define a rectangular ROI region.
Press hotkey to start selection, click top-left then bottom-right.
"""
from __future__ import annotations

import os
import sys
import logging
from typing import Optional, Tuple

import keyboard
import pydirectinput

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from engine.mapper import find_window, get_client_origin_and_size, is_window_minimized, set_process_dpi_awareness


# Hotkey to start ROI selection
ROI_SELECT_HOTKEY = "ctrl+shift+r"


def _get_cursor_pos() -> Tuple[int, int]:
    """Get current cursor position."""
    try:
        import win32api
        return win32api.GetCursorPos()
    except ImportError:
        import ctypes
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return point.x, point.y


def select_roi(hwnd: int, ref_size: Tuple[int, int], render_rect: Tuple[int, int, int, int]) -> None:
    """
    Interactive ROI selection by clicking two points.
    
    Args:
        hwnd: Window handle
        ref_size: Reference resolution (w, h)
        render_rect: Render area (x, y, w, h)
    """
    print("\n" + "="*60)
    print("ROI RECTANGLE SELECTOR")
    print("="*60)
    print("Instructions:")
    print("  1. Click on the TOP-LEFT corner of your ROI")
    print("  2. Click on the BOTTOM-RIGHT corner of your ROI")
    print("  3. ROI coordinates will be generated!")
    print("\nWaiting for first click (top-left)...")
    print("="*60)
    
    points = []
    
    def on_click():
        """Capture click position."""
        if is_window_minimized(hwnd):
            print("ERROR: Window is minimized!")
            return
        
        x, y = _get_cursor_pos()
        
        # Convert to reference coordinates
        render_x, render_y, render_w, render_h = render_rect
        scale_x = render_w / ref_size[0] if ref_size[0] else 1.0
        scale_y = render_h / ref_size[1] if ref_size[1] else 1.0
        ref_x = int(round((x - render_x) / scale_x)) if scale_x else 0
        ref_y = int(round((y - render_y) / scale_y)) if scale_y else 0
        
        points.append((ref_x, ref_y))
        
        if len(points) == 1:
            print(f"\n✓ Point 1 (top-left): screen=({x}, {y}) ref=({ref_x}, {ref_y})")
            print("\nNow click BOTTOM-RIGHT corner...")
        elif len(points) == 2:
            print(f"✓ Point 2 (bottom-right): screen=({x}, {y}) ref=({ref_x}, {ref_y})")
            
            # Calculate ROI
            x1, y1 = points[0]
            x2, y2 = points[1]
            
            # Ensure top-left and bottom-right are correct
            roi_x = min(x1, x2)
            roi_y = min(y1, y2)
            roi_w = abs(x2 - x1)
            roi_h = abs(y2 - y1)
            
            print("\n" + "="*60)
            print("ROI GENERATED!")
            print("="*60)
            print(f"\nTop-left:     ({roi_x}, {roi_y})")
            print(f"Bottom-right: ({roi_x + roi_w}, {roi_y + roi_h})")
            print(f"Size:         {roi_w}x{roi_h}")
            print("\nAdd this to your code:")
            print("="*60)
            print(f"roi_ref=({roi_x}, {roi_y}, {roi_w}, {roi_h})  # x, y, w, h")
            print("="*60)
            print("\nPress Ctrl+Shift+R to select another ROI")
            
            points.clear()
            print("\n" + "="*60)
            print("Ready for next ROI selection...")
            print("Waiting for first click (top-left)...")
            print("="*60)
    
    # Register click hotkey (using mouse button)
    # We'll use a simple polling approach since keyboard doesn't handle mouse
    import time
    import threading
    
    last_click_time = 0
    
    def mouse_poller():
        nonlocal last_click_time
        import ctypes
        while True:
            time.sleep(0.05)
            # Check if left mouse button is pressed
            if ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000:
                current_time = time.time()
                # Debounce - only register if 0.3s passed since last click
                if current_time - last_click_time > 0.3:
                    last_click_time = current_time
                    on_click()
    
    thread = threading.Thread(target=mouse_poller, daemon=True)
    thread.start()


def main():
    """Main entry point."""
    set_process_dpi_awareness()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    # Load config
    config_path = os.path.join(PARENT_DIR, "config.json")
    if not os.path.exists(config_path):
        print(f"ERROR: Config file not found: {config_path}")
        return
    
    import json
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Find window
    target_cfg = config.get("target", {})
    window_title = target_cfg.get("window_title_substring", "")
    
    hwnd = find_window(window_title)
    if not hwnd:
        print(f"ERROR: Could not find window with title containing: '{window_title}'")
        return
    
    print(f"Found window: {window_title}")
    
    # Get reference resolution
    ref_cfg = config.get("reference_resolution", {})
    ref_w = ref_cfg.get("w", 1920)
    ref_h = ref_cfg.get("h", 1080)
    ref_size = (ref_w, ref_h)
    
    # Get render area
    try:
        origin_x, origin_y, client_w, client_h = get_client_origin_and_size(hwnd)
    except Exception as e:
        print(f"ERROR: Failed to get window metrics: {e}")
        return
    
    render_cfg = config.get("render_area", {})
    mode = render_cfg.get("mode", "stretch")
    
    # Calculate render rect (simplified - using stretch mode)
    if mode == "stretch":
        render_rect = (origin_x, origin_y, client_w, client_h)
    else:
        # For fit/manual modes, this is simplified
        render_rect = (origin_x, origin_y, client_w, client_h)
    
    print("\n" + "="*60)
    print("ROI RECTANGLE SELECTOR - READY")
    print("="*60)
    print(f"Hotkey: {ROI_SELECT_HOTKEY} - Start ROI selection")
    print(f"Reference resolution: {ref_w}x{ref_h}")
    print(f"Window size: {client_w}x{client_h}")
    print("="*60)
    
    # Start ROI selection mode
    select_roi(hwnd, ref_size, render_rect)
    
    print("\nROI selector is running...")
    print("Click on the game window to select points")
    print("Press Ctrl+C to exit\n")
    
    try:
        while True:
            keyboard.wait()
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
