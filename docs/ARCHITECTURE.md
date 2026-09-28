# Architecture

```
Camera / upload -> preprocess -> onion segmentation -> per-onion measurements (AI)
   diameter (mm) | rot | sprout | damage % | stain %
                                   |
                       Rules engine (versioned standard)
                                   |
          per-onion: Grade A / URS / Rejected(+category)
                                   |
             lot decision + explanation + integrity hash
                                   |
                 PostgreSQL/SQLite  -> PDF report + QR verify
```

| Layer | Where | Notes |
|---|---|---|
| Web app | `frontend/` | Vanilla JS SPA, mobile-friendly, camera capture via `<input capture>` |
| API | `backend/app/routers` | FastAPI, JWT auth, roles: admin, operator, farmer |
| Vision | `backend/app/services/vision` | `classical.py` (OpenCV baseline) or `yolo_backend.py` (trained model) behind one interface |
| Rules | `backend/app/services/grading.py` | Standards are data (JSON), validated, versioned, snapshotted into every report |
| Reports | `backend/app/services/report.py` | PDF via ReportLab, SHA-256 seal, QR to public verify page |
| Training | `ml/` | Dataset spec, training script, synthetic dry-run |

## Design decisions
- **AI measures, rules decide.** Procurement specs change; a new standard version is a config publish, not a retrain.
- **Every report snapshots the standard it used**, so old reports stay explainable after rules change.
- **Explainability:** each onion carries reasons; each lot carries pass/fail lines against the thresholds.
- **Tamper evidence:** report contents are hashed at creation; `/api/reports/verify/{id}` recomputes and compares.
- **Edge-cut onions are excluded** rather than mis-measured, and the report says how many.
- **Access control:** farmers only see their own batches and reports; only admins publish standards.

## Data model
`Centre` - `User(role)` - `Farmer` - `Batch` - `Inspection` (standard snapshot, counts, decision, hash) - `InspectionImage` - `OnionResult`; `QualityStandard(version, is_active)`.

## Known limits of the baseline
Classical thresholds assume plain background, diffuse light, and one onion layer. Skin colour variation (streaky varieties)
can raise false stain readings. Use the YOLO backend and a labelled dataset for production accuracy.
