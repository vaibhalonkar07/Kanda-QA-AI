from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Observation:
    """What the vision layer measured for one onion. Grading is applied separately."""
    contour: np.ndarray            # Nx1x2 int32 outline in (resized) image pixels
    bbox: tuple[int, int, int, int]  # x, y, w, h
    diameter_px: float
    diameter_mm: float | None
    rot: bool
    sprouted: bool
    damage_pct: float
    discolouration_pct: float
    confidence: float
    truncated: bool = False        # touches the image border -> excluded from counts


@dataclass
class ImageAnalysis:
    image: np.ndarray              # BGR image actually analysed (possibly downscaled)
    observations: list[Observation]
    mm_per_pixel: float | None
    calibration_method: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Calibration:
    mm_per_pixel: float | None = None      # relative to the ORIGINAL image
    scene_width_mm: float | None = None    # real width covered by the image (fixed camera rig)
    marker_size_mm: float | None = None    # side of an ArUco 4x4 marker placed in the scene
