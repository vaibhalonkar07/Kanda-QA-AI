# API summary (interactive docs at `/docs`)

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | any | Get a bearer token |
| POST | `/api/auth/register-farmer` | public | Farmer self-registration |
| POST | `/api/auth/users` | admin | Create operator/admin |
| POST/GET | `/api/farmers` | operator, admin | Register / search farmers |
| POST/GET | `/api/batches` | operator, admin (farmers: GET own) | Register batch, list |
| POST | `/api/batches/{id}/inspections` | operator, admin | Multipart: `files[]`, optional `marker_size_mm`, `mm_per_pixel`, `scene_width_mm`, `notes` |
| GET | `/api/inspections`, `/api/inspections/{id}` | any (scoped) | History, full detail |
| GET | `/api/inspections/{id}/report.pdf` | any (scoped) | PDF report |
| GET | `/api/inspections/{id}/images/{imageId}/{original\|annotated}` | any (scoped) | Images |
| GET | `/api/reports/verify/{reportId}` | public | Integrity check |
| GET/POST | `/api/standards`, `/api/standards/active`, `/api/standards/{id}/activate` | read: any, write: admin | Versioned rules |
| GET | `/api/dashboard/summary` | any (scoped) | KPIs |
| GET | `/api/demo/sample-image.jpg` | public | Synthetic tray with 40 mm marker |
