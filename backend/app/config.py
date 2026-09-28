import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'onion_qa.db'}")
        self.secret_key = os.getenv("SECRET_KEY", "dev-only-secret-change-me-in-production-0000")
        self.token_minutes = int(os.getenv("TOKEN_MINUTES", "720"))
        self.storage_dir = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage")))
        self.vision_backend = os.getenv("VISION_BACKEND", "classical").lower()
        self.yolo_model_path = os.getenv("YOLO_MODEL_PATH", str(BASE_DIR / "models" / "onion_seg.pt"))
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "12"))
        self.max_images = int(os.getenv("MAX_IMAGES", "10"))
        self.max_side_px = int(os.getenv("MAX_SIDE_PX", "2000"))
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        self.seed_demo = os.getenv("SEED_DEMO", "true").lower() == "true"
        self.frontend_dir = Path(os.getenv("FRONTEND_DIR", str(BASE_DIR.parent / "frontend")))


settings = Settings()
settings.storage_dir.mkdir(parents=True, exist_ok=True)
