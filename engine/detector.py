from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import cv2
import numpy as np

from .capture import ScreenCapture
from .mapper import map_point


@dataclass(frozen=True)
class PixelPoint:
    x: int
    y: int
    rgb: Tuple[int, int, int]
    tolerance: int


def parse_pixel_points(raw: Optional[Iterable[dict]]) -> list[PixelPoint]:
    points: list[PixelPoint] = []
    if not raw:
        return points
    for item in raw:
        if "rgb" in item and isinstance(item["rgb"], (list, tuple)) and len(item["rgb"]) == 3:
            r, g, b = item["rgb"]
        else:
            r, g, b = item.get("r"), item.get("g"), item.get("b")
        try:
            point = PixelPoint(
                x=int(item["x"]),
                y=int(item["y"]),
                rgb=(int(r), int(g), int(b)),
                tolerance=int(item.get("tolerance", 0)),
            )
        except Exception:
            continue
        points.append(point)
    return points


class TemplateDetector:
    def __init__(self, template_path: str) -> None:
        self.template_path = template_path
        self._template_gray: Optional[np.ndarray] = None
        self._template_mask: Optional[np.ndarray] = None
        self._missing_logged = False
        self._scaled_cache: dict[Tuple[int, int], Tuple[np.ndarray, Optional[np.ndarray]]] = {}
        self._load_template()

    def reload(self, template_path: Optional[str] = None) -> None:
        if template_path:
            self.template_path = template_path
        self._template_gray = None
        self._template_mask = None
        self._scaled_cache.clear()
        self._missing_logged = False
        self._load_template()

    def _load_template(self) -> None:
        if not self.template_path:
            return
        if not os.path.exists(self.template_path):
            return
        raw = cv2.imread(self.template_path, cv2.IMREAD_UNCHANGED)
        if raw is None or raw.size == 0:
            return
        if raw.ndim == 3 and raw.shape[2] == 4:
            bgr = raw[:, :, :3]
            alpha = raw[:, :, 3]
            self._template_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            self._template_mask = (alpha > 0).astype(np.uint8) * 255
            logging.info("Loaded template with alpha mask: %s", self.template_path)
        elif raw.ndim == 3:
            self._template_gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        else:
            self._template_gray = raw
        logging.info("Loaded template: %s", self.template_path)

    def _get_scaled_template(
        self, scale_x: float, scale_y: float
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if self._template_gray is None:
            return None, None
        t_h, t_w = self._template_gray.shape[:2]
        target_w = max(1, int(round(t_w * scale_x)))
        target_h = max(1, int(round(t_h * scale_y)))
        if target_w == t_w and target_h == t_h:
            return self._template_gray, self._template_mask
        key = (target_w, target_h)
        cached = self._scaled_cache.get(key)
        if cached is not None:
            return cached
        interp = cv2.INTER_AREA if target_w < t_w or target_h < t_h else cv2.INTER_LINEAR
        resized = cv2.resize(self._template_gray, (target_w, target_h), interpolation=interp)
        mask = None
        if self._template_mask is not None:
            mask = cv2.resize(self._template_mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
        self._scaled_cache[key] = (resized, mask)
        return resized, mask

    def match(self, image_bgr: np.ndarray, scale_x: float = 1.0, scale_y: float = 1.0) -> float:
        if self._template_gray is None:
            if not self._missing_logged:
                logging.warning("Template missing or unreadable: %s", self.template_path)
                self._missing_logged = True
            return 0.0
        try:
            image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        except Exception:
            return 0.0
        template, mask = self._get_scaled_template(scale_x, scale_y)
        if template is None:
            return 0.0
        t_h, t_w = template.shape[:2]
        i_h, i_w = image_gray.shape[:2]
        if t_h > i_h or t_w > i_w:
            return 0.0
        score, _loc, _second = self._match_with_location(image_gray, template, mask)
        return float(score)

    def match_with_location(
        self, image_bgr: np.ndarray, scale_x: float = 1.0, scale_y: float = 1.0
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]], Optional[float]]:
        if self._template_gray is None:
            if not self._missing_logged:
                logging.warning("Template missing or unreadable: %s", self.template_path)
                self._missing_logged = True
            return 0.0, None, None, None
        try:
            image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        except Exception:
            return 0.0, None, None, None
        template, mask = self._get_scaled_template(scale_x, scale_y)
        if template is None:
            return 0.0, None, None, None
        t_h, t_w = template.shape[:2]
        i_h, i_w = image_gray.shape[:2]
        if t_h > i_h or t_w > i_w:
            return 0.0, None, None, None
        score, loc, second_best = self._match_with_location(image_gray, template, mask)
        return float(score), loc, (t_w, t_h), float(second_best)

    @staticmethod
    def _match_with_location(
        image_gray: np.ndarray, template: np.ndarray, mask: Optional[np.ndarray]
    ) -> Tuple[float, Tuple[int, int], float]:
        if mask is not None:
            result = cv2.matchTemplate(image_gray, template, cv2.TM_CCORR_NORMED, mask=mask)
        else:
            result = cv2.matchTemplate(image_gray, template, cv2.TM_CCOEFF_NORMED)
        result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
        flat = result.reshape(-1)
        max_idx = int(flat.argmax())
        max_val = float(flat[max_idx])
        width = result.shape[1]
        max_loc = (max_idx % width, max_idx // width)
        if flat.size > 1:
            second_val = float(np.partition(flat, -2)[-2])
        else:
            second_val = max_val
        return max_val, (int(max_loc[0]), int(max_loc[1])), second_val


class FeatureDetector:
    def __init__(self, template_path: str, nfeatures: int = 500) -> None:
        self.template_path = template_path
        self._template_gray: Optional[np.ndarray] = None
        self._template_mask: Optional[np.ndarray] = None
        self._missing_logged = False
        self._orb = cv2.ORB_create(nfeatures=nfeatures)
        self._kp: list[cv2.KeyPoint] = []
        self._desc: Optional[np.ndarray] = None
        self._last_good = 0
        self._last_total = 0
        self._load_template()

    def reload(self, template_path: Optional[str] = None) -> None:
        if template_path:
            self.template_path = template_path
        self._template_gray = None
        self._template_mask = None
        self._kp = []
        self._desc = None
        self._missing_logged = False
        self._load_template()

    def _load_template(self) -> None:
        if not self.template_path:
            return
        if not os.path.exists(self.template_path):
            return
        raw = cv2.imread(self.template_path, cv2.IMREAD_UNCHANGED)
        if raw is None or raw.size == 0:
            return
        if raw.ndim == 3 and raw.shape[2] == 4:
            bgr = raw[:, :, :3]
            alpha = raw[:, :, 3]
            self._template_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            self._template_mask = (alpha > 0).astype(np.uint8) * 255
            logging.info("Loaded feature template with alpha mask: %s", self.template_path)
        elif raw.ndim == 3:
            self._template_gray = cv2.cvtColor(raw, cv2.COLOR_BGR2GRAY)
        else:
            self._template_gray = raw
        if self._template_gray is None:
            return
        self._kp, self._desc = self._orb.detectAndCompute(self._template_gray, self._template_mask)
        self._last_good = 0
        self._last_total = len(self._kp)
        logging.info(
            "Loaded feature template: %s (keypoints=%d)",
            self.template_path,
            len(self._kp),
        )

    def match(self, image_bgr: np.ndarray, scale_x: float = 1.0, scale_y: float = 1.0) -> float:
        score, _loc, _size, _second = self.match_with_location(image_bgr, scale_x, scale_y)
        return float(score)

    def match_with_location(
        self, image_bgr: np.ndarray, scale_x: float = 1.0, scale_y: float = 1.0
    ) -> Tuple[float, Optional[Tuple[int, int]], Optional[Tuple[int, int]], Optional[float]]:
        if self._template_gray is None or self._desc is None or not self._kp:
            if not self._missing_logged:
                logging.warning("Feature template missing or unreadable: %s", self.template_path)
                self._missing_logged = True
            return 0.0, None, None, None
        try:
            image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        except Exception:
            return 0.0, None, None, None
        kp2, desc2 = self._orb.detectAndCompute(image_gray, None)
        if desc2 is None or not kp2:
            self._last_good = 0
            self._last_total = len(self._kp)
            return 0.0, None, None, None
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        matches = matcher.knnMatch(self._desc, desc2, k=2)
        good: list[cv2.DMatch] = []
        for pair in matches:
            if len(pair) != 2:
                continue
            m, n = pair
            if n.distance <= 0:
                continue
            if m.distance < 0.75 * n.distance:
                good.append(m)
        self._last_good = len(good)
        self._last_total = len(self._kp)
        score = len(good) / max(1, len(self._kp))
        if len(good) < 2:
            return float(score), None, None, None
        src_pts = np.float32([self._kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        h, w = self._template_gray.shape[:2]
        homography = None
        if len(good) >= 4:
            homography, _mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if homography is not None:
            corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
            transformed = cv2.perspectiveTransform(corners, homography)
            xs = transformed[:, 0, 0]
            ys = transformed[:, 0, 1]
        else:
            xs = dst_pts[:, 0, 0]
            ys = dst_pts[:, 0, 1]
        left = int(np.min(xs))
        top = int(np.min(ys))
        right = int(np.max(xs))
        bottom = int(np.max(ys))
        width = max(1, right - left)
        height = max(1, bottom - top)
        return float(score), (left, top), (width, height), None

    @property
    def last_good(self) -> int:
        return self._last_good

    @property
    def last_total(self) -> int:
        return self._last_total


def _within_tolerance(sample_rgb: Tuple[int, int, int], expected_rgb: Tuple[int, int, int], tol: int) -> bool:
    return (
        abs(sample_rgb[0] - expected_rgb[0]) <= tol
        and abs(sample_rgb[1] - expected_rgb[1]) <= tol
        and abs(sample_rgb[2] - expected_rgb[2]) <= tol
    )


def _sample_point_from_roi(
    roi_bgr: np.ndarray,
    roi_screen_rect: Tuple[int, int, int, int],
    screen_point: Tuple[int, int],
) -> Optional[Tuple[int, int, int]]:
    left, top, width, height = roi_screen_rect
    x, y = screen_point
    if x < left or y < top or x >= left + width or y >= top + height:
        return None
    rel_x = x - left
    rel_y = y - top
    if rel_y >= roi_bgr.shape[0] or rel_x >= roi_bgr.shape[1]:
        return None
    b, g, r = roi_bgr[rel_y, rel_x]
    return int(r), int(g), int(b)


def pixel_points_check(
    points: Iterable[PixelPoint],
    marker_roi_bgr: np.ndarray,
    marker_roi_screen_rect: Tuple[int, int, int, int],
    ref_size: Tuple[int, int],
    client_origin: Tuple[int, int],
    client_size: Tuple[int, int],
    capture: ScreenCapture,
) -> Tuple[bool, float]:
    points_list = list(points)
    if not points_list:
        return False, 0.0
    matches = 0
    for point in points_list:
        screen_x, screen_y = map_point((point.x, point.y), ref_size, client_origin, client_size)
        sample_rgb = _sample_point_from_roi(
            marker_roi_bgr,
            marker_roi_screen_rect,
            (screen_x, screen_y),
        )
        if sample_rgb is None:
            pixel_img = capture.grab((screen_x, screen_y, 1, 1))
            if pixel_img is None or pixel_img.size == 0:
                continue
            b, g, r = pixel_img[0, 0]
            sample_rgb = (int(r), int(g), int(b))
        if _within_tolerance(sample_rgb, point.rgb, point.tolerance):
            matches += 1
    score = matches / len(points_list)
    return matches == len(points_list), float(score)


class RoiDeltaDetector:
    def __init__(self, delta_threshold: float, smoothing: int = 0) -> None:
        self.delta_threshold = float(delta_threshold)
        self.smoothing = int(smoothing) if smoothing else 0
        self._baseline: Optional[np.ndarray] = None

    def reset(self) -> None:
        self._baseline = None

    def update(self, roi_bgr: np.ndarray) -> Tuple[float, bool]:
        try:
            gray = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2GRAY)
        except Exception:
            return 0.0, False
        gray_f = gray.astype(np.float32)
        if self._baseline is None:
            self._baseline = gray_f
            return 0.0, False
        diff = cv2.absdiff(gray_f, self._baseline)
        score = float(np.mean(diff))
        detected = score >= self.delta_threshold
        if self.smoothing and self.smoothing > 1:
            alpha = 1.0 / float(self.smoothing)
            self._baseline = (1.0 - alpha) * self._baseline + alpha * gray_f
        else:
            if not detected:
                self._baseline = gray_f
        return score, detected
