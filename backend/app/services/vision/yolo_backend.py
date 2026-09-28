"""Optional YOLO instance-segmentation backend (Ultralytics).

Expected model classes (see ../../../../ml/dataset.yaml):
    onion, rot, damage, sprout, stain
Per-onion defect areas are computed from the defect masks that fall inside each onion mask.
Install with: pip install -r requirements-ml.txt
"""
from __future__ import annotations

import cv2
import numpy as np

from .calibration import estimate_scale
from .types import Calibration, ImageAnalysis, Observation

ROT_MIN_PCT = 4.0
_model = None


def load(path: str):
    global _model
    if _model is None:
        from ultralytics import YOLO  # imported lazily so the base install stays light
        _model = YOLO(path)
    return _model


def _poly_mask(xy: np.ndarray, shape) -> np.ndarray:
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [xy.astype(np.int32)], 1)
    return m.astype(bool)


def analyse(bgr: np.ndarray, cal: Calibration, resize_factor: float, model_path: str, conf: float = 0.25) -> ImageAnalysis:
    model = load(model_path)
    h, w = bgr.shape[:2]
    warnings: list[str] = []
    mm_px, method, _ = estimate_scale(bgr, resize_factor, cal)
    if mm_px is None:
        warnings.append("No calibration supplied: diameters cannot be measured and size rules are skipped.")
    res = model.predict(bgr, conf=conf, verbose=False, retina_masks=False)[0]
    names = res.names
    onions, defects = [], {"rot": [], "damage": [], "sprout": [], "stain": []}
    if res.masks is not None:
        for poly, box in zip(res.masks.xy, res.boxes):
            if len(poly) < 3:
                continue
            label = names[int(box.cls)]
            item = (_poly_mask(poly, (h, w)), float(box.conf), poly)
            if label == "onion":
                onions.append(item)
            elif label in defects:
                defects[label].append(item)
    observations: list[Observation] = []
    for mask, c, poly in onions:
        area = int(mask.sum())
        if area < 50:
            continue
        cnt = poly.astype(np.int32).reshape(-1, 1, 2)
        x, y, bw, bh = cv2.boundingRect(cnt)
        truncated = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
        (_, _), (a1, a2), _ = cv2.fitEllipse(cnt) if len(cnt) >= 5 else ((0, 0), (bw, bh), 0)
        diam_px = float(min(a1, a2))

        def frac(kind: str) -> float:
            tot = np.zeros_like(mask)
            for m, _, _ in defects[kind]:
                inside = m & mask
                if inside.sum() > 0.5 * m.sum():
                    tot |= inside
            return 100.0 * tot.sum() / area

        rot, dmg, stain = frac("rot"), frac("damage"), frac("stain")
        sprouted = any(
            (m & cv2.dilate(mask.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)).any()
            for m, _, _ in defects["sprout"]
        )
        observations.append(Observation(
            contour=cnt, bbox=(x, y, bw, bh), diameter_px=diam_px,
            diameter_mm=diam_px * mm_px if mm_px else None,
            rot=rot >= ROT_MIN_PCT, sprouted=sprouted,
            damage_pct=round(min(100.0, rot + dmg), 1),
            discolouration_pct=round(min(100.0, stain + dmg), 1),
            confidence=round(c, 2), truncated=truncated,
        ))
    observations.sort(key=lambda o: (o.bbox[1] // 100, o.bbox[0]))
    return ImageAnalysis(bgr, observations, mm_px, method, warnings)
