from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("NEUROVISTA_HOST", "127.0.0.1")
    port: int = int(os.getenv("NEUROVISTA_PORT", "8000"))
    max_upload_bytes: int = int(os.getenv("NEUROVISTA_MAX_UPLOAD_MB", "256")) * 1024**2
    max_decompressed_bytes: int = int(os.getenv("NEUROVISTA_MAX_DECOMPRESSED_MB", "768")) * 1024**2
    session_ttl_minutes: int = int(os.getenv("NEUROVISTA_SESSION_TTL_MINUTES", "120"))
    verified_demo_dir: Path = Path(os.getenv(
        "NEUROVISTA_VERIFIED_DEMO_DIR",
        Path(__file__).resolve().parents[2] / ".tmp" / "prediction-import-BRATS_457",
    ))
    inference_url: str = os.getenv("NEUROVISTA_INFERENCE_URL", "").rstrip("/")
    inference_token: str = os.getenv("NEUROVISTA_INFERENCE_TOKEN", "")
    inference_connect_timeout_seconds: float = float(os.getenv("NEUROVISTA_INFERENCE_CONNECT_TIMEOUT_SECONDS", "10"))
    inference_transfer_timeout_seconds: float = float(os.getenv("NEUROVISTA_INFERENCE_TRANSFER_TIMEOUT_SECONDS", "300"))


settings = Settings()

