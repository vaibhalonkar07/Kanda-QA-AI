# Kanda QA - AI onion quality inspection (SIH26031)

Computer-vision grading of onion lots for procurement centres: detects rotten, damaged, sprouted and undersized onions,
measures diameter in mm, applies a **configurable, versioned procurement standard** to produce Grade A / URS / rejected
results, and issues an instant PDF quality report with a QR-verifiable integrity seal.

## Run it (2 minutes)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://localhost:8000 (API docs at /docs).

Demo logins (created when `SEED_DEMO=true`; **disable in production**):

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@12345` |
| Operator | `operator1` | `Operator@12345` |
| Farmer | `farmer1` | `Farmer@12345` |

Sign in as the operator -> *New inspection* -> **Use demo tray image** -> *Run inspection*.

## Docker (PostgreSQL)
```bash
cp .env.example .env    # set SECRET_KEY
docker compose up --build
```

## Tests
```bash
cd backend && pytest -q
```
Covers grading rules, vision accuracy against synthetic ground truth, and the whole API flow (RBAC, PDF, verification, standards).

## Layout
```
backend/app/
  routers/            auth, farmers, batches, inspections, standards, dashboard, demo
  services/grading.py rules engine (standards as versioned JSON)
  services/vision/    classical OpenCV baseline, YOLO backend, calibration, synthetic trays
  services/report.py  PDF + SHA-256 integrity seal
frontend/             SPA served by FastAPI
ml/                   dataset spec, training script, synthetic dry-run
docs/                 architecture, API, presentation notes
```

## Taking photos that measure correctly
Plain matte tray, diffuse light, camera pointing straight down, onions fully inside the frame and not stacked.
Include a printed **ArUco 4x4** marker of known size (enter its side length in mm), or use a fixed rig and enter the tray width.

## Before real use
- Replace the placeholder thresholds in the default standard with the current official specification (Admin -> Standards).
- The OpenCV baseline is heuristic. Train the YOLO model with `ml/` for production accuracy, then set `VISION_BACKEND=yolo`.
- Set a strong `SECRET_KEY`, turn off `SEED_DEMO`, serve over HTTPS.
