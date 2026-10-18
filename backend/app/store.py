from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
from threading import RLock
import uuid

import nibabel as nib
import numpy as np

from .imaging import ScanMetadata


@dataclass
class SessionData:
    id: str
    directory: Path
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scan_img: nib.Nifti1Image | None = None
    scan: np.ndarray | None = None
    metadata: ScanMetadata | None = None
    scan_name: str | None = None
    mask_img: nib.Nifti1Image | None = None
    mask: np.ndarray | None = None
    mask_name: str | None = None
    mask_kind: str | None = None
    labels: list[int] = field(default_factory=list)
    synthetic: bool = False


class SessionStore:
    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="neurovista-"))
        self.sessions: dict[str, SessionData] = {}
        self.lock = RLock()

    def create(self) -> SessionData:
        with self.lock:
            session_id = uuid.uuid4().hex
            directory = self.root / session_id
            directory.mkdir()
            session = SessionData(session_id, directory)
            self.sessions[session_id] = session
            return session

    def get(self, session_id: str) -> SessionData:
        with self.lock:
            if session_id not in self.sessions:
                raise KeyError(session_id)
            return self.sessions[session_id]

    def delete(self, session_id: str) -> bool:
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if not session:
                return False
            shutil.rmtree(session.directory, ignore_errors=True)
            return True


store = SessionStore()

