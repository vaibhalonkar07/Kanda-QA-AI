"""Synthetic onion-tray images with known ground truth.

Used for: unit tests, the one-click demo image in the UI, and dry-running the ML pipeline
before a real dataset exists. Scale is 3 px/mm; a 40 mm ArUco marker sits in the bottom-right.
"""
from __future__ import annotations

import cv2
import numpy as np

PX_PER_MM = 3.0
MARKER_MM = 40.0
W, H = 1200, 1000

# (kind, diameter_mm, patch_pct)
DEFAULT_SPEC = (
    [("healthy", d, 0) for d in (56, 60, 62, 64, 66, 58, 68)]
    + [("healthy", 40, 0), ("bruise", 60, 8)]
    + [("healthy", 30, 0), ("healthy", 30, 0)]
    + [("rot", 62, 12), ("rot", 58, 14)]
    + [("sprout", 62, 0)]
    + [("bruise", 64, 22)]
)


def _marker(size_px: int) -> np.ndarray:
    d = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, "generateImageMarker"):
        return cv2.aruco.generateImageMarker(d, 7, size_px)
    return cv2.aruco.drawMarker(d, 7, size_px)  # pragma: no cover


def render_tray(spec=DEFAULT_SPEC, seed: int = 0, with_marker: bool = True):
    """Return (bgr_image, truth) where truth is a list of dicts with masks and labels."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), 236, np.uint8)
    img = np.clip(img + rng.normal(0, 1.5, img.shape), 0, 255).astype(np.uint8)
    truth = []
    cols, rows = 5, 3
    cells = [(c, r) for r in range(rows) for c in range(cols)]
    for idx, (kind, d_mm, pct) in enumerate(spec[: len(cells)]):
        c, r = cells[idx]
        cx = int(40 + c * 225 + 112 + rng.integers(-6, 7))
        cy = int(60 + r * 270 + 112 + rng.integers(-6, 7))
        R = d_mm * PX_PER_MM / 2
        yy, xx = np.mgrid[0:H, 0:W]
        body = ((xx - cx) ** 2 + (yy - cy) ** 2) <= R * R
        base = np.array([90, 60, 150], np.float32) + rng.normal(0, 6, 3)  # BGR red-purple
        rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(R, 1)
        shade = np.clip(1.0 - 0.18 * rr ** 2, 0.8, 1.0)[..., None]
        layer = (base * shade)
        noise = rng.normal(0, 3, (H, W, 1))
        layer = np.clip(layer + noise, 0, 255)
        img[body] = layer[body].astype(np.uint8)
        patch = np.zeros((H, W), bool)
        sprout = np.zeros((H, W), bool)
        if kind in ("rot", "bruise") and pct > 0:
            pr = R * np.sqrt(pct / 100.0)
            ox, oy = cx + 0.35 * (R - pr), cy + 0.25 * (R - pr)
            patch = (((xx - ox) ** 2 + (yy - oy) ** 2) <= pr * pr) & body
            color = (25, 20, 25) if kind == "rot" else (140, 175, 205)
            img[patch] = color
        if kind == "sprout":
            sp = np.zeros((H, W), np.uint8)
            cv2.ellipse(sp, (cx, int(cy - R - 12)), (14, 42), 0, 0, 360, 255, -1)
            sprout = sp > 0
            img[sprout] = (50, 170, 60)
        truth.append({"kind": kind, "diameter_mm": d_mm, "patch_pct": pct, "center": (cx, cy),
                      "onion_mask": body, "patch_mask": patch, "sprout_mask": sprout})
    if with_marker:
        m = _marker(int(MARKER_MM * PX_PER_MM))
        m3 = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
        x0, y0 = W - 30 - m3.shape[1], H - 20 - m3.shape[0]
        img[y0:y0 + m3.shape[0], x0:x0 + m3.shape[1]] = m3
    return img, truth


def render_jpeg(seed: int = 0) -> bytes:
    img, _ = render_tray(seed=seed)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes()
