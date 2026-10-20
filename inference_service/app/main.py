from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hmac
import json
import multiprocessing as mp
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Literal
import uuid
import zipfile

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import settings
from .inference import CHANNEL_ORDER, load_and_validate, run_inference

app = FastAPI(title="NeuroVista GPU Inference", version="0.1.0",
              description="Authenticated research-only MONAI BraTS inference worker")
root = Path(tempfile.mkdtemp(prefix="neurovista-inference-"))
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu-worker")
jobs_lock = threading.RLock()


@dataclass
class Job:
    id: str
    directory: Path
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None
    result: Path | None = None


jobs: dict[str, Job] = {}
rate_windows: dict[str, deque[float]] = defaultdict(deque)
cleanup_stop = threading.Event()


def authenticate(authorization: str | None = Header(None)) -> str:
    if not settings.api_token:
        raise HTTPException(503, "Inference service credential is not configured.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, settings.api_token):
        raise HTTPException(401, "Invalid inference service credential.", headers={"WWW-Authenticate": "Bearer"})
    now = time.monotonic(); window = rate_windows[token]
    while window and window[0] < now - 60: window.popleft()
    if len(window) >= settings.requests_per_minute:
        raise HTTPException(429, "Request limit exceeded; retry after one minute.")
    window.append(now)
    return token


async def save_upload(upload: UploadFile, target: Path, remaining: list[int]) -> None:
    name = upload.filename or ""
    if not (name.lower().endswith(".nii") or name.lower().endswith(".nii.gz")):
        raise HTTPException(415, "Each sequence must be a .nii or .nii.gz file.")
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk); remaining[0] -= len(chunk)
                if size > settings.max_file_mb * 1024**2:
                    raise HTTPException(413, "One sequence exceeds the per-file limit.")
                if remaining[0] < 0:
                    raise HTTPException(413, "The four-sequence request exceeds the total limit.")
                output.write(chunk)
    finally:
        await upload.close()


def child_target(inputs, output_dir, queue):
    try:
        provenance = run_inference(inputs, output_dir, settings.model_path, settings.model_sha256,
                                   settings.max_decompressed_mb * 1024**2)
        queue.put({"ok": True, "provenance": provenance})
    except Exception as exc:
        queue.put({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def process_job(job_id: str) -> None:
    job = jobs[job_id]; job.status = "running"; job.updated_at = datetime.now(timezone.utc)
    context = mp.get_context("spawn"); queue = context.Queue()
    inputs = {name: next((job.directory / "inputs").glob(f"{name}.nii*")) for name in CHANNEL_ORDER}
    process = context.Process(target=child_target, args=(inputs, job.directory / "output", queue), daemon=False)
    process.start(); process.join(settings.timeout_seconds)
    if process.is_alive():
        process.terminate(); process.join(10); outcome = {"ok": False, "error": "Inference exceeded the configured job timeout."}
    elif queue.empty(): outcome = {"ok": False, "error": "Inference worker exited without a result."}
    else: outcome = queue.get()
    with jobs_lock:
        if outcome["ok"]:
            package = job.directory / "neurovista_prediction_package.zip"
            with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.write(job.directory / "output" / "neurovista_ai_prediction.nii.gz", "neurovista_ai_prediction.nii.gz")
                archive.write(job.directory / "output" / "neurovista_ai_prediction_provenance.json", "neurovista_ai_prediction_provenance.json")
            job.result, job.status = package, "completed"
            shutil.rmtree(job.directory / "inputs", ignore_errors=True)
        else:
            job.status, job.error = "failed", outcome["error"]
            shutil.rmtree(job.directory, ignore_errors=True)
        job.updated_at = datetime.now(timezone.utc)


def cleanup_expired() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.retention_minutes)
    with jobs_lock:
        expired = [key for key, job in jobs.items() if job.status in ("completed", "failed") and job.updated_at < cutoff]
        for key in expired:
            shutil.rmtree(jobs[key].directory, ignore_errors=True); del jobs[key]


def cleanup_loop() -> None:
    while not cleanup_stop.wait(60): cleanup_expired()


threading.Thread(target=cleanup_loop, name="retention-cleaner", daemon=True).start()


@app.get("/health")
def health():
    return {"status": "ok", "service": "NeuroVista GPU inference", "model": "MONAI brats_mri_segmentation",
            "model_version": "0.5.4", "authenticated_jobs": True, "research_only": True}


@app.post("/v1/jobs", status_code=202)
async def submit_job(t1c: UploadFile = File(...), t1: UploadFile = File(...), t2: UploadFile = File(...),
                     flair: UploadFile = File(...), _token: str = Depends(authenticate)):
    cleanup_expired()
    with jobs_lock:
        active = sum(job.status in ("queued", "running") for job in jobs.values())
        if active >= settings.max_queued_jobs + 1:
            raise HTTPException(429, "Inference queue is full; retry later.")
    job_id = uuid.uuid4().hex; directory = root / job_id; inputs_dir = directory / "inputs"; inputs_dir.mkdir(parents=True)
    remaining = [settings.max_total_mb * 1024**2]
    try:
        for name, upload in (("t1c", t1c), ("t1", t1), ("t2", t2), ("flair", flair)):
            suffix = ".nii.gz" if (upload.filename or "").lower().endswith(".nii.gz") else ".nii"
            await save_upload(upload, inputs_dir / f"{name}{suffix}", remaining)
        inputs = {name: next(inputs_dir.glob(f"{name}.nii*")) for name in CHANNEL_ORDER}
        load_and_validate(inputs, settings.max_decompressed_mb * 1024**2)
    except ValueError as exc:
        shutil.rmtree(directory, ignore_errors=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception:
        shutil.rmtree(directory, ignore_errors=True); raise
    job = Job(job_id, directory)
    with jobs_lock: jobs[job_id] = job
    executor.submit(process_job, job_id)
    return job_payload(job)


def job_payload(job: Job):
    return {"job_id": job.id, "status": job.status, "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(), "error": job.error,
            "result_available": job.status == "completed" and bool(job.result and job.result.is_file())}


@app.get("/v1/jobs/{job_id}")
def job_status(job_id: str, _token: str = Depends(authenticate)):
    cleanup_expired()
    with jobs_lock:
        job = jobs.get(job_id)
        if not job: raise HTTPException(404, "Job was not found or has expired.")
        return job_payload(job)


@app.get("/v1/jobs/{job_id}/result")
def job_result(job_id: str, _token: str = Depends(authenticate)):
    cleanup_expired()
    with jobs_lock:
        job = jobs.get(job_id)
        if not job: raise HTTPException(404, "Job was not found or has expired.")
        if job.status != "completed" or not job.result or not job.result.is_file():
            raise HTTPException(409, f"Result is not ready; job is {job.status}.")
        return FileResponse(job.result, media_type="application/zip", filename="neurovista_prediction_package.zip")


@app.on_event("shutdown")
def shutdown():
    cleanup_stop.set(); executor.shutdown(wait=False, cancel_futures=True); shutil.rmtree(root, ignore_errors=True)

