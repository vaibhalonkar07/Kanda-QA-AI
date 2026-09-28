# Kanda-QA-AI
# Kanda QA - AI Onion Quality Inspection

**Smart India Hackathon 2026 - Problem Statement SIH26031**

An AI-assisted inspection system for onion procurement centres. It uses computer vision to detect rotten, damaged, sprouted and undersized onions, measures each bulb in millimetres, grades the lot as **Grade A / URS / Rejected** against a configurable procurement standard, and issues an instant, verifiable digital quality report.

> Subjective manual inspection -> standardised visual inspection -> objective measurements -> rules-based grading -> instant report -> fewer disputes.

![Annotated inspection sample](docs/images/annotated-sample.jpg)

*Synthetic demo tray: each onion is outlined by grade (green = Grade A, amber = URS, red = rejected) and labelled with its measured diameter.*

---

## Features

- **AI inspection:** onion detection, touching-onion separation, rot, sprout and damage/stain detection
- **Size measurement:** diameter in mm using an ArUco reference marker, a fixed-rig tray width, or a known mm-per-pixel value
- **Rules engine:** the AI measures, a versioned standard decides the grade, so a change in procurement rules is a config update, not a retrain
- **Explainable results:** per-onion reasons and pass/fail lines for the lot decision
- **Digital report:** PDF with breakdown, annotated images, QR code and SHA-256 integrity hash
- **Public verification:** anyone with a report ID can confirm the record is unchanged
- **Roles:** admin, operator and farmer; farmers only see their own batches and reports
- **History and dashboard:** every inspection, image and standard version is stored
- **Two vision backends:** ready-to-run OpenCV baseline, and an optional trained YOLO segmentation model

## How it works

```
Camera / upload -> preprocess -> onion segmentation -> per-onion measurements (AI)
   diameter (mm) | rot | sprout | damage % | stain %
                              |
                  Rules engine (versioned standard)
                              |
        per-onion: Grade A / URS / Rejected (+ category)
                              |
          lot decision + explanation + integrity hash
                              |
               Database -> PDF report + QR verification
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla JavaScript SPA (no build step), mobile friendly |
| Backend | Python, FastAPI, SQLAlchemy, JWT auth |
| Vision | OpenCV (baseline), Ultralytics YOLO segmentation (optional) |
| Database | SQLite (default), PostgreSQL (Docker) |
| Reports | ReportLab (PDF + QR) |

## Quick start

### Windows (PowerShell)

Requires Python 3.11 or 3.12 with "Add python.exe to PATH" ticked during install.

```powershell
git clone https://github.com/<your-username>/onion-quality-ai.git
cd onion-quality-ai\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### macOS / Linux

```bash
git clone https://github.com/<your-username>/onion-quality-ai.git
cd onion-quality-ai/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://localhost:8000** (interactive API docs at `/docs`).

### Docker (PostgreSQL)

```bash
cp .env.example .env     # set SECRET_KEY
docker compose up --build
```

## Demo

Demo accounts are created when `SEED_DEMO=true`. **Disable this in production.**

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `Admin@12345` |
| Operator | `operator1` | `Operator@12345` |
| Farmer | `farmer1` | `Farmer@12345` |

1. Sign in as `operator1` and open **New inspection**.
2. Pick a farmer, click **Use demo tray image**, then **Run inspection**.
3. Review the composition band, the "Why this result" section and the annotated image.
4. Download the PDF, then open the public verification link.
5. Sign in as `admin`, open **Standards**, change a limit and publish a new version. New reports use the new version; old reports keep theirs.

## Taking photos that measure correctly

- Plain, matte, single-colour tray with diffuse light (no hard shadows)
- Camera pointing straight down at a fixed height
- Onions fully inside the frame, not stacked or overlapping heavily
- A printed **ArUco 4x4** marker of known size in the frame (enter its side length in mm), or a fixed rig with a known tray width

Onions cut off by the image edge are excluded and reported rather than mis-measured.

## Configuring the grading standard

Standards are JSON, validated and versioned. Admins publish a new version from **Standards** in the UI (or `POST /api/standards`). Every report stores a snapshot of the standard it used.

```json
{
  "size_mm": { "grade_a_min": 45, "grade_a_max": 80, "urs_min": 35, "urs_max": 90 },
  "onion_limits": {
    "grade_a": { "damage_pct": 5,  "discolouration_pct": 10 },
    "urs":     { "damage_pct": 15, "discolouration_pct": 25 }
  },
  "reject_if": { "rotten": true, "sprouted": true },
  "lot": { "grade_a_min_pct": 75, "urs_min_pct": 85, "max_rotten_pct": 3, "min_onions_for_decision": 30 }
}
```

> **Important:** the default values are illustrative placeholders. Replace them with the thresholds from the current official procurement specification before real use.

## Upgrading to a trained model

The OpenCV baseline works without data but is heuristic. For production accuracy, train the YOLO segmentation model:

```bash
pip install -r backend/requirements-ml.txt
cd ml
python train_yolo.py train --data dataset.yaml --epochs 100
cp runs/segment/onion/weights/best.pt ../backend/models/onion_seg.pt
```

Then set `VISION_BACKEND=yolo`. See [`ml/README.md`](ml/README.md) for the data collection and labelling plan. `ml/make_synthetic_dataset.py` generates synthetic data to dry-run the training pipeline only.

## Project structure

```
backend/app/
  routers/              auth, farmers, batches, inspections, standards, dashboard, demo
  services/grading.py   rules engine
  services/vision/      OpenCV baseline, YOLO backend, calibration, synthetic trays
  services/report.py    PDF report + integrity hash
frontend/               single-page web app served by FastAPI
ml/                     dataset spec, training script, synthetic dry run
docs/                   architecture, API summary, presentation notes
```

## Tests

```bash
cd backend
pytest -q
```

Covers the grading rules, vision accuracy against synthetic ground truth, and the full API flow (role-based access, PDF, verification, standards).

## API

Interactive documentation is served at `/docs`. A summary is in [`docs/API.md`](docs/API.md).

## Known limitations

- Baseline vision assumes a plain background, diffuse light and a single layer of onions; streaky skin varieties can raise false stain readings.
- Baseline accuracy has been validated on synthetic images only. Validate on real photos against calipers and an experienced assessor before deployment.
- Default grading thresholds are placeholders (see above).

## Security notes

Set a strong `SECRET_KEY`, set `SEED_DEMO=false`, and serve over HTTPS in any real deployment.

## Contributing

Issues and pull requests are welcome. Please run `pytest -q` before submitting.

## License

Add a license before publishing (for example MIT) and place it in a `LICENSE` file.
