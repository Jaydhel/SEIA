from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import logging
import os
import math
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import pydirectinput

from .capture import ScreenCapture
from .detector import FeatureDetector, TemplateDetector
from .mapper import (
    find_window,
    get_client_origin_and_size,
    is_window_minimized,
    map_rect,
    focus_window,
    set_process_dpi_awareness,
)
from .verify import verify_match, add_pixel_verification, get_last_failed_offset, get_last_verified_points


def _get_cursor_pos() -> Tuple[int, int]:
    point = wintypes.POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        return int(point.x), int(point.y)
    return 0, 0


@dataclass(frozen=True)
class MatchResult:
    score: float
    top_left: Tuple[int, int]
    center: Tuple[int, int]
    template_size: Tuple[int, int]
    ref_center: Tuple[int, int]
    second_best: Optional[float] = None
    score_delta: Optional[float] = None
    method: str = "template"
    match_count: Optional[int] = None
    match_total: Optional[int] = None


class AutomationEngine:
    def __init__(self, config_path: str = "config.json") -> None:
        set_process_dpi_awareness()
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._hwnd: Optional[int] = None
        self._capture = ScreenCapture()
        self._templates: Dict[str, TemplateDetector | FeatureDetector] = {}
        self._use_pixel_verification = False
        self._debug_screenshot = False
        self._debug_output_dir = "debug_out"
        self._load_config()

    def _load_config(self) -> None:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Missing config: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)
        target = self._config.get("target", {})
        self._title_substring = target.get("window_title_substring", "")
        self._process_name = target.get("process_name", "") or None
        ref = self._config.get("reference_resolution", {})
        self._ref_size = (int(ref.get("w", 1920)), int(ref.get("h", 1080)))
        self._render_cfg = self._config.get("render_area", {"mode": "stretch"})
        marker_cfg = self._config.get("marker_detection", {})
        self._default_threshold = float(marker_cfg.get("threshold", 0.85))
        self._default_min_score_delta = float(marker_cfg.get("min_score_delta", 0.0))
        self._use_pixel_verification = bool(marker_cfg.get("use_pixel_verification", False))
        self._detector_method = str(marker_cfg.get("method", "template")).lower()
        if self._detector_method not in {"template", "feature"}:
            self._detector_method = "template"
        input_cfg = self._config.get("input", {})
        self._mouse_motion = str(input_cfg.get("mouse_motion", "instant")).lower()
        self._mouse_motion_duration = max(0.0, float(input_cfg.get("mouse_motion_duration_ms", 0.0)) / 1000.0)
        self._mouse_motion_fps = max(1.0, float(input_cfg.get("mouse_motion_fps", 60.0)))
        self._mouse_jitter_px = max(0.0, float(input_cfg.get("mouse_jitter_px", 0.0)))
        if self._mouse_motion not in {"instant", "linear", "ease", "human"}:
            self._mouse_motion = "instant"
        debug_cfg = self._config.get("debug", {})
        self._debug_screenshot = bool(debug_cfg.get("screenshot", False))
        debug_output = debug_cfg.get("output_dir", "debug_out")
        self._debug_output_dir = str(debug_output) if debug_output else "debug_out"
        poll_ms = self._config.get("poll_interval_ms", 50)
        self._poll_interval = max(0.01, float(poll_ms) / 1000.0)

    def reload(self) -> None:
        self._load_config()
        self._templates.clear()
        self._hwnd = None

    def _ensure_window(self) -> int:
        if self._hwnd is None:
            self._hwnd = find_window(self._title_substring, self._process_name)
            if self._hwnd is None:
                raise RuntimeError("Target window not found.")
        return self._hwnd

    def focus_window(self) -> bool:
        hwnd = self._ensure_window()
        return focus_window(hwnd)

    @staticmethod
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

    def _get_window_metrics(
        self,
    ) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int, int, int], float, float]:
        hwnd = self._ensure_window()
        if is_window_minimized(hwnd):
            raise RuntimeError("Window is minimized.")
        origin_x, origin_y, client_w, client_h = get_client_origin_and_size(hwnd)
        if client_w == 0 or client_h == 0:
            raise RuntimeError("Client size is zero.")
        render_x, render_y, render_w, render_h = self._compute_render_rect(
            (origin_x, origin_y), (client_w, client_h), self._ref_size, self._render_cfg
        )
        scale_x = render_w / self._ref_size[0] if self._ref_size[0] else 1.0
        scale_y = render_h / self._ref_size[1] if self._ref_size[1] else 1.0
        return (origin_x, origin_y), (client_w, client_h), (render_x, render_y, render_w, render_h), scale_x, scale_y

    def _get_template(self, image_path: str) -> TemplateDetector | FeatureDetector:
        detector = self._templates.get(image_path)
        if detector is None:
            if self._detector_method == "feature":
                detector = FeatureDetector(image_path)
            else:
                detector = TemplateDetector(image_path)
            self._templates[image_path] = detector
        return detector

    def _capture_roi(
        self,
        roi_ref: Optional[Tuple[int, int, int, int]],
        render_rect: Tuple[int, int, int, int],
    ) -> Tuple[Tuple[int, int, int, int], Optional[Any]]:
        ref_w, ref_h = self._ref_size
        if roi_ref is None:
            roi_ref = (0, 0, ref_w, ref_h)
        roi_screen = map_rect(roi_ref, self._ref_size, (render_rect[0], render_rect[1]), (render_rect[2], render_rect[3]))
        image = self._capture.grab(roi_screen)
        return roi_screen, image

    def _resolve_threshold(self, threshold: Optional[float], use_default_threshold: bool) -> float:
        if threshold is not None:
            return float(threshold)
        if use_default_threshold:
            return self._default_threshold
        return 0.0

    def default_min_score_delta(self) -> float:
        return float(self._default_min_score_delta)

    def locate_image(
        self,
        image_path: str,
        roi_ref: Optional[Tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        use_default_threshold: bool = True,
        min_score_delta: Optional[float] = None,
    ) -> Optional[MatchResult]:
        _, _, render_rect, scale_x, scale_y = self._get_window_metrics()
        roi_screen, image = self._capture_roi(roi_ref, render_rect)
        if image is None:
            return None
        detector = self._get_template(image_path)
        score, loc, size, _second_best = detector.match_with_location(image, scale_x, scale_y)
        if loc is None or size is None or not math.isfinite(score):
            return None
        min_score = self._resolve_threshold(threshold, use_default_threshold)
        if score < min_score:
            logging.debug(f"Rejecting match: score={score:.3f} < threshold={min_score:.3f}")
            return None
        delta = None
        if _second_best is not None and math.isfinite(_second_best):
            delta = float(score - _second_best)
            logging.debug(f"Match delta check: score={score:.3f}, second={_second_best:.3f}, delta={delta:.3f}")
        min_delta = self._default_min_score_delta if min_score_delta is None else float(min_score_delta)
        logging.debug(f"min_delta={min_delta:.3f}, delta={delta}, condition: min_delta > 0.0 = {min_delta > 0.0}, delta is not None = {delta is not None}, delta < min_delta = {delta < min_delta if delta is not None else 'N/A'}")
        if min_delta > 0.0 and delta is not None and delta < min_delta:
            logging.warning(
                f"REJECTING MATCH: delta={delta:.3f} < min_delta={min_delta:.3f} "
                f"(score={score:.3f}, second={_second_best:.3f})"
            )
            return None
        top_left = (roi_screen[0] + loc[0], roi_screen[1] + loc[1])
        
        # Pixel verification check (if enabled)
        if self._use_pixel_verification:
            image_filename = os.path.basename(image_path)
            verification_passed = verify_match(image, loc, image_filename)

            if self._debug_screenshot:
                try:
                    import cv2

                    debug_img = image.copy()
                    debug_dir = self._debug_output_dir
                    if not os.path.isabs(debug_dir):
                        debug_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), debug_dir)
                    os.makedirs(debug_dir, exist_ok=True)

                    if verification_passed:
                        for (rel_x, rel_y) in get_last_verified_points():
                            abs_x = loc[0] + rel_x
                            abs_y = loc[1] + rel_y
                            cv2.circle(debug_img, (abs_x, abs_y), 5, (0, 255, 0), -1)
                        cv2.rectangle(debug_img, loc, (loc[0] + size[0], loc[1] + size[1]), (0, 255, 0), 2)
                        debug_path = os.path.join(debug_dir, f"verify_pass_{image_filename}")
                        cv2.imwrite(debug_path, debug_img)
                        logging.info("Debug screenshot saved: %s", debug_path)
                    else:
                        failed_offset = get_last_failed_offset()
                        if failed_offset is not None:
                            abs_x = loc[0] + failed_offset[0]
                            abs_y = loc[1] + failed_offset[1]
                            cv2.circle(debug_img, (abs_x, abs_y), 5, (0, 0, 255), -1)
                        cv2.rectangle(debug_img, loc, (loc[0] + size[0], loc[1] + size[1]), (0, 0, 255), 2)
                        debug_path = os.path.join(debug_dir, f"verify_fail_{image_filename}")
                        cv2.imwrite(debug_path, debug_img)
                        logging.info("Debug screenshot saved: %s", debug_path)
                except Exception as exc:
                    logging.debug("Failed to save debug screenshot: %s", exc)
            
            if not verification_passed:
                logging.warning(f"REJECTING MATCH: Pixel verification failed for {image_filename}")
                return None
        
        center = (top_left[0] + size[0] // 2, top_left[1] + size[1] // 2)
        ref_x = int(round((center[0] - render_rect[0]) / scale_x)) if scale_x else 0
        ref_y = int(round((center[1] - render_rect[1]) / scale_y)) if scale_y else 0
        method = "feature" if isinstance(detector, FeatureDetector) else "template"
        match_count = None
        match_total = None
        if isinstance(detector, FeatureDetector):
            match_count = detector.last_good
            match_total = detector.last_total
        return MatchResult(
            score=score,
            top_left=top_left,
            center=center,
            template_size=size,
            ref_center=(ref_x, ref_y),
            second_best=_second_best,
            score_delta=delta,
            method=method,
            match_count=match_count,
            match_total=match_total,
        )

    def image_present(
        self,
        image_path: str,
        roi_ref: Optional[Tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        use_default_threshold: bool = True,
    ) -> bool:
        return (
            self.locate_image(
                image_path,
                roi_ref=roi_ref,
                threshold=threshold,
                use_default_threshold=use_default_threshold,
            )
            is not None
        )

    def wait_for_image(
        self,
        image_path: str,
        roi_ref: Optional[Tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        use_default_threshold: bool = True,
        timeout_s: float = 5.0,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[MatchResult]:
        deadline = time.monotonic() + max(0.0, timeout_s)
        while True:
            if stop_check is not None and stop_check():
                return None
            try:
                result = self.locate_image(
                    image_path,
                    roi_ref=roi_ref,
                    threshold=threshold,
                    use_default_threshold=use_default_threshold,
                )
            except RuntimeError as exc:
                logging.warning("Window not ready: %s", exc)
                result = None
            if result is not None:
                return result
            if timeout_s <= 0:
                return None
            if time.monotonic() >= deadline:
                return None
            if stop_check is not None and stop_check():
                return None
            time.sleep(self._poll_interval)

    def action(
        self,
        image_path: str,
        coords_offset: Tuple[int, int] = (0, 0),
        click_duration: float = 0.0,
        timeout_s: float = 5.0,
        roi_ref: Optional[Tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        use_default_threshold: bool = True,
        offset_in_ref: bool = True,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        result = self.action_with_match(
            image_path,
            coords_offset=coords_offset,
            click_duration=click_duration,
            timeout_s=timeout_s,
            roi_ref=roi_ref,
            threshold=threshold,
            use_default_threshold=use_default_threshold,
            offset_in_ref=offset_in_ref,
            stop_check=stop_check,
        )
        return result is not None

    def action_with_match(
        self,
        image_path: str,
        coords_offset: Tuple[int, int] = (0, 0),
        click_duration: float = 0.0,
        timeout_s: float = 5.0,
        roi_ref: Optional[Tuple[int, int, int, int]] = None,
        threshold: Optional[float] = None,
        use_default_threshold: bool = True,
        offset_in_ref: bool = True,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[MatchResult]:
        result = self.wait_for_image(
            image_path,
            roi_ref=roi_ref,
            threshold=threshold,
            use_default_threshold=use_default_threshold,
            timeout_s=timeout_s,
            stop_check=stop_check,
        )
        if result is None:
            return None
        click_x, click_y = result.center
        if coords_offset != (0, 0):
            _, _, render_rect, scale_x, scale_y = self._get_window_metrics()
            dx, dy = coords_offset
            if offset_in_ref:
                click_x += int(round(dx * scale_x))
                click_y += int(round(dy * scale_y))
            else:
                click_x += int(dx)
                click_y += int(dy)
        self._move_mouse(click_x, click_y)
        self._click_at(click_x, click_y, click_duration)
        return result

    def move_to_screen(self, x: int, y: int, duration: float = 0.0) -> None:
        if duration > 0:
            pydirectinput.moveTo(int(x), int(y), duration=max(0.0, float(duration)))
            return
        self._move_mouse(int(x), int(y))

    def move_to_ref(self, x: int, y: int, duration: float = 0.0) -> None:
        _, _, render_rect, scale_x, scale_y = self._get_window_metrics()
        screen_x = render_rect[0] + int(round(x * scale_x))
        screen_y = render_rect[1] + int(round(y * scale_y))
        if duration > 0:
            pydirectinput.moveTo(int(screen_x), int(screen_y), duration=max(0.0, float(duration)))
            return
        self._move_mouse(int(screen_x), int(screen_y))

    def _move_mouse(self, target_x: int, target_y: int) -> None:
        mode = self._mouse_motion
        if mode == "instant" or self._mouse_motion_duration <= 0:
            pydirectinput.moveTo(int(target_x), int(target_y), duration=0.0)
            return
        start_x, start_y = _get_cursor_pos()
        duration = self._mouse_motion_duration
        steps = max(1, int(round(duration * self._mouse_motion_fps)))
        for step in range(1, steps + 1):
            t = step / steps
            if mode in {"ease", "human"}:
                t = t * t * (3.0 - 2.0 * t)
            x = start_x + (target_x - start_x) * t
            y = start_y + (target_y - start_y) * t
            if mode == "human" and self._mouse_jitter_px > 0.0:
                jitter_scale = 1.0 - abs(0.5 - t) * 2.0
                jitter = self._mouse_jitter_px * jitter_scale
                x += random.uniform(-jitter, jitter)
                y += random.uniform(-jitter, jitter)
            pydirectinput.moveTo(int(round(x)), int(round(y)), duration=0.0)
            if step < steps:
                time.sleep(duration / steps)

    def _click_at(self, x: int, y: int, click_duration: float) -> None:
        if click_duration > 0:
            try:
                pydirectinput.mouseDown()
            except TypeError:
                pydirectinput.mouseDown(int(x), int(y))
            time.sleep(max(0.0, float(click_duration)))
            try:
                pydirectinput.mouseUp()
            except TypeError:
                pydirectinput.mouseUp(int(x), int(y))
            return
        try:
            pydirectinput.click()
        except TypeError:
            pydirectinput.click(int(x), int(y))
