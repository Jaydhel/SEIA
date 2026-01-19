from __future__ import annotations

import logging
import os
import sys

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from engine.runtime import (
    action,
    cleanup,
    hotkey_restart,
    hotkey_stop,
    press,
    hold_key,
    press_until,
    reset_stop,
    sleep,
    wait_for,
    wait_for_restart,
    add_pixel_verification,
)

MARKER1_NEAR = (270, 226)
MARKER1_RADIUS = 250
MARKER2_NEAR = (348,184)
MARKER2_RADIUS = 250
STATECHECK2_NEAR = (1733,65)
STATECHECK2_RADIUS = 300

def run_sequence() -> None:
    action("marker1.png", click_duration=0.5, near=MARKER1_NEAR, radius=MARKER1_RADIUS)
    wait_for("statecheck4.png", 30.0, roi_ref=(212, 150, 317, 62), verify_pixels=[(43, 4, (252, 141, 162), 30)])
    action("marker2.png")
    action("marker3.png", (-50, 0))
    action("marker4.png", (-50, 70))
    action("marker5.png", (-50, 50))
    for i in range(5):
        print('Iteration', i + 1)
        action("marker6.png", (-80, 80 + (120 * i)))
        # Check if press_until succeeded
        found = press_until(
            "statecheck2.png",
            ["1", "space"],
            60.0,
            step_delay_s=0.5,
            roi_ref=(1500, 20, 400, 100),  # x, y, w, h
            verify_pixels=[
                (30, 30, (244, 245, 246), 50)
            ],
            require=False
        )
        if not found: # Only continue if match was found
            print(f'Iteration {i + 1}: statecheck2 not found, skipping to next iteration')
            continue  # Skip rest of loop, go to next iteration
        print(f'Iteration {i + 1}: statecheck2 found, proceeding...') # Match found - proceed with the rest
        hold_key("esc", 2)
        sleep(0.5)
        hold_key("space", 2)  # First space hold
        sleep(3)              # Wait 3 seconds
        hold_key("space", 2, repeat=3)  # Hold space 3 more times
    hold_key("esc", 2)

def main() -> None:
    hotkey_stop("F6")
    hotkey_restart("F5")
    wait_for_restart()
    while True:
        reset_stop()
        try:
            run_sequence()
        except SystemExit:
            pass
        wait_for_restart()

if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
