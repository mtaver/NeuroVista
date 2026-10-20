from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_token: str = os.getenv("NEUROVISTA_INFERENCE_TOKEN", "")
    model_path: Path = Path(os.getenv("NEUROVISTA_MODEL_PATH", "/opt/neurovista/weights/model.pt"))
    model_sha256: str = os.getenv("NEUROVISTA_MODEL_SHA256", "860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae")
    max_file_mb: int = int(os.getenv("NEUROVISTA_INFERENCE_MAX_FILE_MB", "256"))
    max_total_mb: int = int(os.getenv("NEUROVISTA_INFERENCE_MAX_TOTAL_MB", "768"))
    max_decompressed_mb: int = int(os.getenv("NEUROVISTA_INFERENCE_MAX_DECOMPRESSED_MB", "768"))
    max_queued_jobs: int = int(os.getenv("NEUROVISTA_INFERENCE_MAX_QUEUED_JOBS", "2"))
    timeout_seconds: int = int(os.getenv("NEUROVISTA_INFERENCE_TIMEOUT_SECONDS", "900"))
    retention_minutes: int = int(os.getenv("NEUROVISTA_INFERENCE_RETENTION_MINUTES", "30"))
    requests_per_minute: int = int(os.getenv("NEUROVISTA_INFERENCE_REQUESTS_PER_MINUTE", "30"))


settings = Settings()

