from app.services import grading as g
from app.services.vision import analyse_image
from app.services.vision.synthetic import DEFAULT_SPEC, render_tray
from app.services.vision.types import Calibration


def _run(cal):
    img, truth = render_tray()
    return analyse_image(img, cal), truth


def test_detects_every_onion_and_measures_size_with_marker():
    a, truth = _run(Calibration(marker_size_mm=40))
    assert a.calibration_method == "aruco_marker"
    assert len(a.observations) == len(DEFAULT_SPEC)
    measured = sorted(o.diameter_mm for o in a.observations)
    expected = sorted(t["diameter_mm"] for t in truth)
    for m, e in zip(measured, expected):
        assert abs(m - e) / e < 0.06


def test_grades_match_ground_truth():
    a, _ = _run(Calibration(marker_size_mm=40))
    std = g.default_standard()
    grades = [g.grade_onion(g.OnionMeasurement(o.diameter_mm, o.rot, o.sprouted, o.damage_pct, o.discolouration_pct), std)
              for o in a.observations]
    counts, _ = g.summarise(grades)
    assert counts == {"grade_a": 7, "urs": 2, "rotten": 2, "damaged": 1, "sprouted": 1, "undersized": 2, "oversized": 0}


def test_manual_scale_and_no_scale():
    a, _ = _run(Calibration(mm_per_pixel=1 / 3))
    assert a.calibration_method == "manual_mm_per_pixel"
    b, _ = _run(Calibration())
    assert b.calibration_method == "none" and all(o.diameter_mm is None for o in b.observations)
    assert b.warnings
