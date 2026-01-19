from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import mss
import numpy as np


class ScreenCapture:
    def __init__(self) -> None:
        self._sct = mss.mss()

    def grab(self, rect: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        left, top, width, height = rect
        if width <= 0 or height <= 0:
            return None
        monitor = {
            "left": int(left),
            "top": int(top),
            "width": int(width),
            "height": int(height),
        }
        try:
            raw = np.array(self._sct.grab(monitor), dtype=np.uint8)
        except Exception as exc:
            logging.warning("Screen grab failed: %s", exc)
            return None
        try:
            return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
        except Exception as exc:
            logging.warning("Failed to convert capture to BGR: %s", exc)
            return None
