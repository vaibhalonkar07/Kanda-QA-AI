"""Generate a synthetic YOLO-seg dataset to dry-run training end to end (NOT for real accuracy).

    python make_synthetic_dataset.py --n 200
Writes ml/datasets/onion/{images,labels}/{train,val}.
"""
import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.vision.synthetic import DEFAULT_SPEC, H, W, render_tray  # noqa: E402

CLS = {"onion": 0, "rot": 1, "damage": 2, "sprout": 3}


def poly_line(mask: np.ndarray, cls: int) -> str | None:
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 30:
        return None
    c = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
    if len(c) < 3:
        return None
    return f"{cls} " + " ".join(f"{x / W:.5f} {y / H:.5f}" for x, y in c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=str(Path(__file__).parent / "datasets" / "onion"))
    a = ap.parse_args()
    out = Path(a.out)
    kinds = ["healthy"] * 6 + ["bruise", "rot", "sprout"]
    for i in range(a.n):
        rnd = random.Random(i)
        spec = [(rnd.choice(kinds), rnd.randint(30, 72), rnd.choice([6, 10, 14, 20])) for _ in range(15)]
        spec = [(k, d, p if k in ("bruise", "rot") else 0) for k, d, p in spec]
        img, truth = render_tray(spec, seed=i, with_marker=False)
        split = "val" if i % 10 == 0 else "train"
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        lines = []
        for t in truth:
            for key, cls in (("onion_mask", 0), ("patch_mask", 1 if t["kind"] == "rot" else 2), ("sprout_mask", 3)):
                if t[key].any():
                    ln = poly_line(t[key], cls)
                    if ln:
                        lines.append(ln)
        cv2.imwrite(str(out / "images" / split / f"syn_{i:04d}.jpg"), img)
        (out / "labels" / split / f"syn_{i:04d}.txt").write_text("\n".join(lines))
    print("Wrote", a.n, "images to", out)


if __name__ == "__main__":
    main()
