"""Vision entry point: decode -> (resize) -> backend -> ImageAnalysis, plus annotation drawing."""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from ...config import settings
from . import classical
from .types import Calibration, ImageAnalysis

log = logging.getLogger("vision")

GRADE_COLORS = {"GRADE_A": (79, 125, 46), "URS": (14, 124, 194), "REJECT": (30, 38, 179)}  # BGR


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("File is not a readable image")
    return img


def backend_name() -> str:
    if settings.vision_backend == "yolo" and Path(settings.yolo_model_path).exists():
        return "yolo"
    if settings.vision_backend == "yolo":
        log.warning("YOLO model not found at %s - falling back to the classical pipeline", settings.yolo_model_path)
    return "classical"


def analyse_image(bgr_original: np.ndarray, cal: Calibration) -> ImageAnalysis:
    h, w = bgr_original.shape[:2]
    scale = min(1.0, settings.max_side_px / max(h, w))
    bgr = cv2.resize(bgr_original, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA) if scale < 1 else bgr_original
    if backend_name() == "yolo":
        from . import yolo_backend
        return yolo_backend.analyse(bgr, cal, scale, settings.yolo_model_path)
    return classical.analyse(bgr, cal, scale)


def annotate(bgr: np.ndarray, items: list[dict]) -> np.ndarray:
    """items: {contour, number, grade, diameter_mm, excluded}"""
    out = bgr.copy()
    scale = max(0.6, out.shape[1] / 1400)
    for it in items:
        color = (150, 150, 150) if it["excluded"] else GRADE_COLORS[it["grade"]]
        cv2.drawContours(out, [it["contour"]], -1, color, max(2, int(3 * scale)))
        x, y, w, h = cv2.boundingRect(it["contour"])
        d = it["diameter_mm"]
        label = f"#{it['number']}" + (f" {d:.0f}mm" if d else "") + (" (edge)" if it["excluded"] else "")
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale, 1)
        cx, cy = x + w // 2 - tw // 2, y + h // 2 + th // 2
        cv2.rectangle(out, (cx - 3, cy - th - 3), (cx + tw + 3, cy + 4), (255, 255, 255), -1)
        cv2.putText(out, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.55 * scale, color, 1, cv2.LINE_AA)
    return out
