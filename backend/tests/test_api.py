import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/t.db"
os.environ["STORAGE_DIR"] = tempfile.mkdtemp()
os.environ["SEED_DEMO"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.vision.synthetic import render_jpeg  # noqa: E402


def _login(c, u, p):
    r = c.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_flow():
    with TestClient(app) as c:
        op = _login(c, "operator1", "Operator@12345")
        farmer = c.post("/api/farmers", json={"name": "Sunita Jadhav", "village": "Lasalgaon"}, headers=op).json()
        batch = c.post("/api/batches", json={"farmer_id": farmer["id"], "quantity_kg": 850}, headers=op).json()
        assert batch["batch_code"].startswith("ON-")

        files = [("files", ("tray.jpg", render_jpeg(), "image/jpeg"))]
        r = c.post(f"/api/batches/{batch['id']}/inspections", files=files,
               data={"marker_size_mm": "40", "bag_rate_50kg": "1500"}, headers=op)
        assert r.status_code == 201, r.text
        insp = r.json()
        assert insp["total_onions"] == 15
        assert insp["counts"]["grade_a"] == 7
        assert insp["decision"] in ("URS", "REJECTED", "GRADE_A")
        assert insp["bag_rate_50kg"] == 1500
        assert insp["estimated_lot_value"] == 25500

        invalid_rate = c.post(f"/api/batches/{batch['id']}/inspections", files=files,
                      data={"bag_rate_50kg": "0"}, headers=op)
        assert invalid_rate.status_code == 422

        pdf = c.get(f"/api/inspections/{insp['id']}/report.pdf", headers=op)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        img = c.get(f"/api/inspections/{insp['id']}/images/{insp['images'][0]['id']}/annotated", headers=op)
        assert img.status_code == 200

        v = c.get(f"/api/reports/verify/{insp['report_id']}").json()
        assert v["integrity_ok"] is True
        assert v["bag_rate_50kg"] == 1500 and v["estimated_lot_value"] == 25500

        # farmers only see their own data
        fa = _login(c, "farmer1", "Farmer@12345")
        assert c.get("/api/batches", headers=fa).json() == []
        assert c.get(f"/api/inspections/{insp['id']}", headers=fa).status_code == 404
        assert c.post(f"/api/batches/{batch['id']}/inspections", files=files, headers=fa).status_code == 403

        # bad upload is rejected clearly
        bad = c.post(f"/api/batches/{batch['id']}/inspections", files=[("files", ("x.jpg", b"nope", "image/jpeg"))], headers=op)
        assert bad.status_code == 422

        # standards: only admin publishes, and invalid configs are refused
        ad = _login(c, "admin", "Admin@12345")
        active = c.get("/api/standards/active", headers=ad).json()
        assert c.post("/api/standards", json={"name": "x-standard", "config": active["config"]}, headers=op).status_code == 403
        cfg = active["config"]
        cfg["size_mm"]["grade_a_min"] = 5
        assert c.post("/api/standards", json={"name": "bad-standard", "config": cfg}, headers=ad).status_code == 422
        cfg["size_mm"]["grade_a_min"] = 50
        ok = c.post("/api/standards", json={"name": "Updated standard", "config": cfg}, headers=ad)
        assert ok.status_code == 201 and ok.json()["version"] == 2

        summary = c.get("/api/dashboard/summary", headers=ad).json()
        assert summary["inspections"] == 1 and summary["batches"] == 1
