"""Pixel -> millimetre scale estimation."""
from __future__ import annotations

import cv2
import numpy as np


def detect_aruco(bgr: np.ndarray, marker_size_mm: float):
    """Find a 4x4 ArUco marker of known side length. Returns (mm_per_px, polygon) or None."""
    if not hasattr(cv2, "aruco"):
        return None
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
        corners, ids, _ = detector.detectMarkers(gray)
    except Exception:  # older/newer OpenCV API differences
        return None
    if ids is None or len(corners) == 0:
        return None
    pts = corners[0].reshape(4, 2)
    side_px = float(np.mean([np.linalg.norm(pts[i] - pts[(i + 1) % 4]) for i in range(4)]))
    if side_px < 8:
        return None
    return marker_size_mm / side_px, pts.astype(np.int32)


def estimate_scale(bgr: np.ndarray, resize_factor: float, cal) -> tuple[float | None, str, np.ndarray | None]:
    """Priority: ArUco marker > explicit mm/pixel > scene width > none.

    `resize_factor` is analysed_size / original_size, so an explicit mm/pixel measured on the
    original image is converted to the analysed image.
    """
    if cal.marker_size_mm:
        found = detect_aruco(bgr, float(cal.marker_size_mm))
        if found:
            return found[0], "aruco_marker", found[1]
    if cal.mm_per_pixel:
        return float(cal.mm_per_pixel) / resize_factor, "manual_mm_per_pixel", None
    if cal.scene_width_mm:
        return float(cal.scene_width_mm) / bgr.shape[1], "scene_width", None
    return None, "none", None
