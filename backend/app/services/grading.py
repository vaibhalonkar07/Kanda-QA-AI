"""Procurement rules engine.

The AI only *measures* (diameter, defect areas, rot, sprouting). This module applies a
configurable, versioned standard to those measurements. Nothing here is hard-wired to a
particular year's rules: admins publish a new standard version when the specification changes.

NOTE: DEFAULT_STANDARD values are illustrative placeholders. Replace them with the thresholds
from the current official procurement specification before real use.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

GRADE_A, URS, REJECT = "GRADE_A", "URS", "REJECT"
REJECT_CATEGORIES = ("rotten", "damaged", "sprouted", "undersized", "oversized")
COUNT_KEYS = ("grade_a", "urs") + REJECT_CATEGORIES

DEFAULT_STANDARD: dict = {
    "note": "Illustrative placeholder thresholds - replace with the current official specification.",
    "size_mm": {"grade_a_min": 45.0, "grade_a_max": 80.0, "urs_min": 35.0, "urs_max": 90.0},
    "onion_limits": {
        "grade_a": {"damage_pct": 5.0, "discolouration_pct": 10.0},
        "urs": {"damage_pct": 15.0, "discolouration_pct": 25.0},
    },
    "reject_if": {"rotten": True, "sprouted": True},
    "lot": {
        "grade_a_min_pct": 75.0,      # lot is GRADE_A if Grade A share >= this
        "urs_min_pct": 85.0,          # else lot is URS if (Grade A + URS) share >= this
        "max_rotten_pct": 3.0,        # lot is REJECTED if rotten share exceeds this
        "min_onions_for_decision": 30,  # below this the report carries a low-sample warning
    },
}


def default_standard() -> dict:
    return copy.deepcopy(DEFAULT_STANDARD)


def validate_standard(cfg: dict) -> dict:
    """Raise ValueError if the config is malformed or internally inconsistent."""
    try:
        s = cfg["size_mm"]
        for k in ("grade_a_min", "grade_a_max", "urs_min", "urs_max"):
            float(s[k])
        if not (0 < s["urs_min"] <= s["grade_a_min"] < s["grade_a_max"] <= s["urs_max"]):
            raise ValueError("size_mm must satisfy urs_min <= grade_a_min < grade_a_max <= urs_max")
        for grade in ("grade_a", "urs"):
            for k in ("damage_pct", "discolouration_pct"):
                v = float(cfg["onion_limits"][grade][k])
                if not 0 <= v <= 100:
                    raise ValueError(f"onion_limits.{grade}.{k} must be 0-100")
        if cfg["onion_limits"]["grade_a"]["damage_pct"] > cfg["onion_limits"]["urs"]["damage_pct"]:
            raise ValueError("Grade A damage limit cannot exceed the URS damage limit")
        for k in ("grade_a_min_pct", "urs_min_pct", "max_rotten_pct"):
            v = float(cfg["lot"][k])
            if not 0 <= v <= 100:
                raise ValueError(f"lot.{k} must be 0-100")
        if cfg["lot"]["urs_min_pct"] > 100 or cfg["lot"]["grade_a_min_pct"] > cfg["lot"]["urs_min_pct"]:
            raise ValueError("lot.grade_a_min_pct cannot exceed lot.urs_min_pct")
        int(cfg["lot"]["min_onions_for_decision"])
        cfg.setdefault("reject_if", {"rotten": True, "sprouted": True})
    except KeyError as e:
        raise ValueError(f"Missing field in standard: {e}") from e
    except (TypeError, ValueError) as e:
        raise ValueError(str(e)) from e
    return cfg


@dataclass
class OnionMeasurement:
    diameter_mm: float | None
    rot: bool
    sprouted: bool
    damage_pct: float          # total visible defect area (rot + lesions), % of onion surface
    discolouration_pct: float  # lesion / staining area, % of onion surface


@dataclass
class OnionGrade:
    grade: str
    category: str
    reasons: list[str] = field(default_factory=list)


def grade_onion(m: OnionMeasurement, std: dict) -> OnionGrade:
    size, lim, rej = std["size_mm"], std["onion_limits"], std.get("reject_if", {})
    d = m.diameter_mm

    if m.rot and rej.get("rotten", True):
        return OnionGrade(REJECT, "rotten", ["Rot / black decay detected"])
    if m.sprouted and rej.get("sprouted", True):
        return OnionGrade(REJECT, "sprouted", ["Green sprout detected"])
    if d is not None and d < size["urs_min"]:
        return OnionGrade(REJECT, "undersized", [f"Diameter {d:.1f} mm is below the {size['urs_min']:g} mm minimum"])
    if d is not None and d > size["urs_max"]:
        return OnionGrade(REJECT, "oversized", [f"Diameter {d:.1f} mm is above the {size['urs_max']:g} mm maximum"])
    urs = lim["urs"]
    if m.damage_pct > urs["damage_pct"] or m.discolouration_pct > urs["discolouration_pct"]:
        return OnionGrade(
            REJECT, "damaged",
            [f"Surface damage {m.damage_pct:.1f}% / staining {m.discolouration_pct:.1f}% exceed URS limits"],
        )

    a = lim["grade_a"]
    reasons: list[str] = []
    if d is not None and not (size["grade_a_min"] <= d <= size["grade_a_max"]):
        reasons.append(f"Diameter {d:.1f} mm is outside the Grade A range")
    if m.damage_pct > a["damage_pct"]:
        reasons.append(f"Surface damage {m.damage_pct:.1f}% exceeds the Grade A limit of {a['damage_pct']:g}%")
    if m.discolouration_pct > a["discolouration_pct"]:
        reasons.append(f"Staining {m.discolouration_pct:.1f}% exceeds the Grade A limit of {a['discolouration_pct']:g}%")
    if m.sprouted:
        reasons.append("Sprout present (tolerated under URS)")
    if m.rot:
        reasons.append("Rot present (tolerated under URS)")
    if reasons:
        return OnionGrade(URS, "healthy", reasons)
    return OnionGrade(GRADE_A, "healthy", [])


def summarise(grades: list[OnionGrade]) -> tuple[dict, dict]:
    counts = {k: 0 for k in COUNT_KEYS}
    for g in grades:
        if g.grade == GRADE_A:
            counts["grade_a"] += 1
        elif g.grade == URS:
            counts["urs"] += 1
        else:
            counts[g.category] += 1
    total = len(grades)
    pct = {k: (round(100.0 * v / total, 1) if total else 0.0) for k, v in counts.items()}
    return counts, pct


def grade_lot(counts: dict, pct: dict, std: dict) -> tuple[str, list[dict], list[str]]:
    """Return (decision, explanation lines, warnings)."""
    lot = std["lot"]
    total = sum(counts.values())
    a_pct, urs_pct, rot_pct = pct["grade_a"], pct["urs"], pct["rotten"]
    accept_pct = round(a_pct + urs_pct, 1)
    expl: list[dict] = []
    warnings: list[str] = []

    if total == 0:
        return "REJECTED", [{"status": "fail", "text": "No onions could be measured in the submitted images."}], [
            "No onions detected"
        ]
    if total < int(lot["min_onions_for_decision"]):
        warnings.append(
            f"Only {total} onions were analysed; at least {lot['min_onions_for_decision']} are recommended for a reliable lot decision."
        )

    rot_ok = rot_pct <= lot["max_rotten_pct"]
    expl.append({
        "status": "pass" if rot_ok else "fail",
        "text": f"Rotten onions {rot_pct:.1f}% (limit {lot['max_rotten_pct']:g}%)",
    })
    a_ok = a_pct >= lot["grade_a_min_pct"]
    expl.append({
        "status": "pass" if a_ok else "fail",
        "text": f"Grade A share {a_pct:.1f}% (needed {lot['grade_a_min_pct']:g}% for a Grade A lot)",
    })
    u_ok = accept_pct >= lot["urs_min_pct"]
    expl.append({
        "status": "pass" if u_ok else "fail",
        "text": f"Grade A + URS share {accept_pct:.1f}% (needed {lot['urs_min_pct']:g}% for a URS lot)",
    })

    if not rot_ok:
        decision = "REJECTED"
    elif a_ok:
        decision = "GRADE_A"
    elif u_ok:
        decision = "URS"
    else:
        decision = "REJECTED"
    labels = {"GRADE_A": "Grade A lot", "URS": "URS lot", "REJECTED": "Lot not eligible"}
    expl.append({"status": "info", "text": f"Decision: {labels[decision]}"})
    return decision, expl, warnings
