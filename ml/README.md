# ML workspace

The backend runs out of the box with the classical OpenCV pipeline. This folder is how you upgrade it to a trained
model once you have labelled photos.

## 1. Collect data
- Photograph onions on a **plain, matte, single-colour tray** under diffuse light (no hard shadows). Fix the camera height.
- Put one printed **ArUco 4x4 marker** (id 7 works; any 4x4_50 id is detected) of known size in every photo, or use a fixed rig with a known tray width.
- Cover: red / light red / white varieties, different harvest lots, dry-skin and wet-skin, wet and dusty conditions, 5-20 onions per photo.
- Aim for 1,500+ photos with all defect classes represented. Split by **lot/day**, not randomly, so validation is honest (no near-duplicate photos across splits).

## 2. Label (polygons)
Classes: `onion`, `rot`, `damage`, `sprout`, `stain` (see `dataset.yaml`). Tools: Roboflow, CVAT, Label Studio.
Have two people label 10% of images and check agreement. Use the official onion quality specification to decide what counts as damage vs. stain.

## 3. Train
```bash
pip install -r ../backend/requirements-ml.txt
python train_yolo.py train --data dataset.yaml --epochs 100
python train_yolo.py val --weights runs/segment/onion/weights/best.pt
cp runs/segment/onion/weights/best.pt ../backend/models/onion_seg.pt
VISION_BACKEND=yolo uvicorn app.main:app   # from ../backend
```

## 4. Dry run without data
`python make_synthetic_dataset.py --n 200` builds a synthetic dataset so you can confirm the training + inference plumbing.
Synthetic accuracy says nothing about real onions.

## 5. Evaluate what matters
Report per-class recall for `rot` and `sprout` (missed defects hurt farmers and buyers alike), diameter error in mm against
calipers on 100+ onions, and batch-level Grade A % against an experienced assessor. Track these per model version.
