"""
Multi-verification system for reliable image detection.
Combines template matching with pixel verification to eliminate false positives.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Tuple, List

import cv2
import numpy as np


class VerifiedMatcher:
    """
    Enhanced matcher that requires both template match AND pixel verification.
    This eliminates false positives by checking actual pixel colors at key positions.
    """
    
    def __init__(self):
        self.verification_points: dict[str, List[Tuple[int, int, Tuple[int, int, int], int]]] = {}
        self.last_verified_points: list[Tuple[int, int]] = []
        self.last_failed_offset: Optional[Tuple[int, int]] = None
        self.last_failed_expected: Optional[Tuple[int, int, int]] = None
        self.last_failed_actual: Optional[Tuple[int, int, int]] = None
    
    def add_verification_points(
        self, 
        image_name: str, 
        points: List[Tuple[int, int, Tuple[int, int, int], int]]
    ) -> None:
        """
        Add pixel verification points for an image.
        
        Args:
            image_name: Name of the template image
            points: List of (x, y, (r, g, b), tolerance) relative to template top-left
                   x, y = offset from match location
                   (r, g, b) = expected RGB color
                   tolerance = allowed difference per channel
        """
        self.verification_points[image_name] = points
    
    def verify_match(
        self,
        screenshot: np.ndarray,
        match_location: Tuple[int, int],
        image_name: str
    ) -> bool:
        """
        Verify a template match by checking pixel colors at specific locations.
        
        Returns:
            True if all verification points match, False otherwise
        """
        self.last_verified_points = []
        self.last_failed_offset = None
        self.last_failed_expected = None
        self.last_failed_actual = None
        if image_name not in self.verification_points:
            logging.warning(f"No verification points defined for {image_name}, accepting match")
            return True
        
        points = self.verification_points[image_name]
        top_x, top_y = match_location
        verified_points = []
        
        for rel_x, rel_y, expected_rgb, tolerance in points:
            abs_x = top_x + rel_x
            abs_y = top_y + rel_y
            
            # Check bounds
            if abs_y >= screenshot.shape[0] or abs_x >= screenshot.shape[1]:
                logging.debug(f"Verification point ({abs_x}, {abs_y}) out of bounds")
                self.last_failed_offset = (rel_x, rel_y)
                return False
            
            # Get actual pixel (BGR in OpenCV)
            b, g, r = screenshot[abs_y, abs_x]
            actual_rgb = (int(r), int(g), int(b))
            
            # Check if within tolerance
            if not self._colors_match(actual_rgb, expected_rgb, tolerance):
                logging.info(
                    f"Pixel verification FAILED at offset ({rel_x}, {rel_y}): "
                    f"expected RGB{expected_rgb} ± {tolerance}, got RGB{actual_rgb}"
                )
                self.last_failed_offset = (rel_x, rel_y)
                self.last_failed_expected = expected_rgb
                self.last_failed_actual = actual_rgb
                return False
            
            verified_points.append((rel_x, rel_y))
        
        logging.debug(f"All {len(points)} verification points matched for {image_name}")
        self.last_verified_points = verified_points
        return True
    
    @staticmethod
    def _colors_match(
        actual: Tuple[int, int, int], 
        expected: Tuple[int, int, int], 
        tolerance: int
    ) -> bool:
        """Check if two RGB colors match within tolerance."""
        return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


# Global instance
_verifier = VerifiedMatcher()


def add_pixel_verification(
    image_name: str,
    points: List[Tuple[int, int, Tuple[int, int, int], int]]
) -> None:
    """
    Add pixel verification points for an image.
    
    Example:
        # Verify that at offset (50, 20) from match, pixel is white (255,255,255) ± 10
        add_pixel_verification("statecheck4.png", [
            (50, 20, (255, 255, 255), 10),
            (100, 30, (0, 128, 255), 15),
        ])
    """
    key = os.path.basename(image_name)
    _verifier.add_verification_points(key, points)


def verify_match(
    screenshot: np.ndarray,
    match_location: Tuple[int, int],
    image_name: str
) -> bool:
    """Verify a template match using pixel checks."""
    key = os.path.basename(image_name)
    return _verifier.verify_match(screenshot, match_location, key)


def get_last_verified_points() -> list[Tuple[int, int]]:
    return list(_verifier.last_verified_points)


def get_last_failed_offset() -> Optional[Tuple[int, int]]:
    return _verifier.last_failed_offset
