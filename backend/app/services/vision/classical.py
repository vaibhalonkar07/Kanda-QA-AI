"""Baseline OpenCV pipeline (no training data needed).

Segmentation : background colour from the image border -> LAB distance -> Otsu -> watershed split
Size         : ellipse fit on the onion body, minor axis = equatorial diameter
Sprouting    : saturated green regions attached to an onion
Rot          : near-black regions inside the onion
Damage/stain : regions that deviate strongly from the onion's own median colour

It is a transparent baseline and a fallback. Swap in the YOLO backend once a labelled dataset exists.
Thresholds live in CLASSICAL_PARAMS so they can be tuned per camera rig.
"""
from __future__ import annotations

import cv2
import numpy as np

from .calibration import estimate_scale
from .types import Calibration, ImageAnalysis, Observation

CLASSICAL_PARAMS = {
    "fg_min_distance": 40,      # min uint8 LAB-distance to count as foreground
    "min_diameter_mm": 15.0,    # ignore smaller blobs when calibrated
    "min_area_frac": 0.0008,    # ignore smaller blobs (fraction of image) when uncalibrated
    "green_h": (35, 85),
    "green_s_min": 70,
    "green_v_min": 60,
    "sprout_min_px": 60,        # green blob area (px) needed to call it a sprout
    "dark_v_max": 60,           # V channel below this = rot / black decay
    "rot_min_pct": 4.0,         # % of surface that is near-black -> onion flagged rotten
    "lesion_delta_lab": 32.0,   # LAB distance from median onion colour = lesion
    "erode_frac": 0.06,         # ignore the rim when measuring surface defects
}
P = CLASSICAL_PARAMS


def _foreground(bgr: np.ndarray, marker_poly: np.ndarray | None) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (5, 5), 0)
    lab = cv2.cvtColor(blur, cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    t = max(4, int(0.04 * min(h, w)))
    border = np.concatenate([
        lab[:t].reshape(-1, 3), lab[-t:].reshape(-1, 3),
        lab[:, :t].reshape(-1, 3), lab[:, -t:].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)
    d8 = np.clip(dist * 2.5, 0, 255).astype(np.uint8)
    if marker_poly is not None:
        pad = cv2.dilate(cv2.fillConvexPoly(np.zeros((h, w), np.uint8), marker_poly, 255),
                         np.ones((15, 15), np.uint8))
        d8[pad > 0] = 0
    thr, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, mask = cv2.threshold(d8, max(thr, P["fg_min_distance"]), 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, cnts, -1, 255, cv2.FILLED)  # fill holes
    return filled


def _green_mask(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lo = (P["green_h"][0], P["green_s_min"], P["green_v_min"])
    hi = (P["green_h"][1], 255, 255)
    return cv2.inRange(hsv, lo, hi)


def _split_touching(binary: np.ndarray, min_area: float) -> np.ndarray:
    """Label image; touching onions are separated with a distance-transform watershed."""
    n, cc, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = [stats[i, cv2.CC_STAT_AREA] for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    if not areas:
        return np.zeros(binary.shape, np.int32)
    median = float(np.median(areas))
    out = np.zeros(binary.shape, np.int32)
    nxt = 1
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue
        comp = (cc == i).astype(np.uint8) * 255
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull_area = cv2.contourArea(cv2.convexHull(cnts[0])) or 1.0
        solidity = area / hull_area
        if area > 1.7 * median or solidity < 0.88:
            dist = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
            sure = (dist > 0.55 * dist.max()).astype(np.uint8)
            n_m, markers = cv2.connectedComponents(sure)
            if n_m > 2:
                markers = markers + 1
                markers[(comp > 0) & (sure == 0)] = 0
                markers[comp == 0] = 1
                cv2.watershed(cv2.cvtColor(comp, cv2.COLOR_GRAY2BGR), markers)
                for m in range(2, n_m + 1):
                    region = markers == m
                    if region.sum() >= min_area:
                        out[region] = nxt
                        nxt += 1
                continue
        out[cc == i] = nxt
        nxt += 1
    return out


def analyse(bgr: np.ndarray, cal: Calibration, resize_factor: float = 1.0) -> ImageAnalysis:
    h, w = bgr.shape[:2]
    warnings: list[str] = []
    mm_px, method, marker_poly = estimate_scale(bgr, resize_factor, cal)
    if cal.marker_size_mm and method != "aruco_marker":
        warnings.append("ArUco marker not found; used the next available calibration method.")
    if mm_px is None:
        warnings.append("No calibration supplied: diameters cannot be measured and size rules are skipped.")

    fg = _foreground(bgr, marker_poly)
    green = _green_mask(bgr)
    green = cv2.bitwise_and(green, fg)
    green_d = cv2.dilate(green, np.ones((5, 5), np.uint8))
    body_fg = cv2.morphologyEx(cv2.bitwise_and(fg, cv2.bitwise_not(green_d)), cv2.MORPH_OPEN,
                               cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

    if mm_px:
        min_area = np.pi / 4 * (P["min_diameter_mm"] / mm_px) ** 2
    else:
        min_area = P["min_area_frac"] * h * w
    labels = _split_touching(body_fg, max(min_area, 30))

    n_labels = int(labels.max())
    green_n, green_cc, green_stats, _ = cv2.connectedComponentsWithStats(green, connectivity=8)
    label_sprout_px: dict[int, int] = {}
    for gi in range(1, green_n):
        g_area = int(green_stats[gi, cv2.CC_STAT_AREA])
        if g_area < P["sprout_min_px"] // 3:
            continue
        near = cv2.dilate((green_cc == gi).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
        vals = labels[near]
        vals = vals[vals > 0]
        if vals.size:
            lab_id = int(np.bincount(vals).argmax())
            label_sprout_px[lab_id] = label_sprout_px.get(lab_id, 0) + g_area

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab_img = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    observations: list[Observation] = []
    for lid in range(1, n_labels + 1):
        mask = (labels == lid).astype(np.uint8) * 255
        if mask.sum() == 0:
            continue
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnt = max(cnts, key=cv2.contourArea)
        if len(cnt) < 5:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        truncated = x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1
        (_, _), (ax1, ax2), _ = cv2.fitEllipse(cnt)
        diam_px = float(min(ax1, ax2))  # equatorial (smaller) axis
        area = cv2.contourArea(cnt)
        solidity = area / (cv2.contourArea(cv2.convexHull(cnt)) or 1.0)

        r = max(3, int(P["erode_frac"] * diam_px))
        inner = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))) > 0
        n_inner = int(inner.sum())
        if n_inner < 20:
            inner = mask > 0
            n_inner = int(inner.sum())

        dark = inner & (hsv[..., 2] < P["dark_v_max"])
        rot_pct = 100.0 * dark.sum() / n_inner
        healthy_px = inner & ~dark
        lesion_pct = 0.0
        if healthy_px.sum() > 20:
            med = np.median(lab_img[healthy_px], axis=0)
            delta = np.linalg.norm(lab_img - med, axis=2)
            lesion = healthy_px & (delta > P["lesion_delta_lab"])
            lesion = cv2.morphologyEx(lesion.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)) > 0
            lesion_pct = 100.0 * lesion.sum() / n_inner

        sprouted = label_sprout_px.get(lid, 0) >= P["sprout_min_px"]
        conf = float(min(0.99, 0.5 + 0.5 * solidity ** 2))
        observations.append(Observation(
            contour=cnt, bbox=(x, y, bw, bh), diameter_px=diam_px,
            diameter_mm=(diam_px * mm_px) if mm_px else None,
            rot=rot_pct >= P["rot_min_pct"], sprouted=sprouted,
            damage_pct=round(min(100.0, rot_pct + lesion_pct), 1),
            discolouration_pct=round(lesion_pct, 1),
            confidence=round(conf, 2), truncated=truncated,
        ))

    if observations:
        row_h = max(1, int(np.median([q.bbox[3] for q in observations])))
        observations.sort(key=lambda o: (o.bbox[1] // row_h, o.bbox[0]))
    return ImageAnalysis(bgr, observations, mm_px, method, warnings)
