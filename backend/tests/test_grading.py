import pytest

from app.services import grading as g


def M(d=60, rot=False, sprout=False, dmg=0, disc=0):
    return g.OnionMeasurement(d, rot, sprout, dmg, disc)


STD = g.default_standard()


def test_healthy_is_grade_a():
    r = g.grade_onion(M(), STD)
    assert (r.grade, r.category) == (g.GRADE_A, "healthy")


def test_small_but_acceptable_is_urs():
    assert g.grade_onion(M(d=40), STD).grade == g.URS


def test_undersized_rejected():
    r = g.grade_onion(M(d=30), STD)
    assert (r.grade, r.category) == (g.REJECT, "undersized")


def test_rot_and_sprout_rejected():
    assert g.grade_onion(M(rot=True), STD).category == "rotten"
    assert g.grade_onion(M(sprout=True), STD).category == "sprouted"


def test_damage_between_limits_is_urs_and_above_is_rejected():
    assert g.grade_onion(M(dmg=8), STD).grade == g.URS
    assert g.grade_onion(M(dmg=20), STD).category == "damaged"


def test_no_calibration_skips_size_rules():
    assert g.grade_onion(M(d=None), STD).grade == g.GRADE_A


def test_sprout_can_be_tolerated_under_urs_when_configured():
    std = g.default_standard()
    std["reject_if"]["sprouted"] = False
    assert g.grade_onion(M(sprout=True), std).grade == g.URS


def test_lot_decisions():
    def lot(a, u, rot):
        counts = {k: 0 for k in g.COUNT_KEYS}
        counts.update(grade_a=a, urs=u, rotten=rot, damaged=100 - a - u - rot)
        pct = {k: float(v) for k, v in counts.items()}
        return g.grade_lot(counts, pct, STD)[0]

    assert lot(80, 10, 1) == "GRADE_A"
    assert lot(60, 30, 1) == "URS"
    assert lot(40, 30, 1) == "REJECTED"
    assert lot(90, 5, 5) == "REJECTED"  # too much rot even though Grade A share is high


def test_low_sample_warning_and_empty_lot():
    counts = {k: 0 for k in g.COUNT_KEYS}
    assert g.grade_lot(counts, {k: 0.0 for k in counts}, STD)[0] == "REJECTED"
    counts["grade_a"] = 10
    pct = {k: 0.0 for k in counts}
    pct["grade_a"] = 100.0
    _, _, warnings = g.grade_lot(counts, pct, STD)
    assert warnings


def test_standard_validation():
    g.validate_standard(g.default_standard())
    bad = g.default_standard()
    bad["size_mm"]["grade_a_min"] = 20
    with pytest.raises(ValueError):
        g.validate_standard(bad)
    with pytest.raises(ValueError):
        g.validate_standard({})
