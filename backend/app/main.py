from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import nibabel as nib
import numpy as np

from .config import settings
from .imaging import (ImagingError, label_measurements, label_mesh, load_nifti, orientation_labels,
                      render_slice, validate_mask)
from .store import SessionData, store
from . import remote_inference

app = FastAPI(title="NeuroVista API", version="0.1.0", description="Local-only MRI research workspace")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


def fail(status: int, message: str) -> None:
    raise HTTPException(status_code=status, detail=message)


def require_scan(session_id: str) -> SessionData:
    try:
        session = store.get(session_id)
    except KeyError:
        fail(404, "Session not found or already cleared.")
    if session.scan is None or session.scan_img is None or session.metadata is None:
        fail(409, "Upload a scan first.")
    return session


async def save_upload(file: UploadFile, target: Path) -> None:
    name = file.filename or ""
    if not (name.lower().endswith(".nii") or name.lower().endswith(".nii.gz")):
        fail(415, "Only .nii and .nii.gz files are accepted.")
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    fail(413, "Upload exceeds the configured size limit.")
                output.write(chunk)
    finally:
        await file.close()


@app.exception_handler(ImagingError)
async def imaging_error_handler(_request, exc: ImagingError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "NeuroVista", "storage": "temporary local files", "ai": "not_connected"}


@app.get("/api/inference/status")
async def inference_status() -> dict:
    return await remote_inference.availability()


@app.post("/api/sessions")
def new_session() -> dict:
    session = store.create()
    return {"session_id": session.id}


@app.delete("/api/sessions/{session_id}")
def clear_session(session_id: str) -> dict:
    return {"cleared": store.delete(session_id)}


@app.post("/api/sessions/{session_id}/scan")
async def upload_scan(session_id: str, file: UploadFile = File(...)) -> dict:
    try:
        session = store.get(session_id)
    except KeyError:
        fail(404, "Session not found.")
    suffix = ".nii.gz" if (file.filename or "").lower().endswith(".nii.gz") else ".nii"
    target = session.directory / f"scan{suffix}"
    await save_upload(file, target)
    image, data, metadata = load_nifti(target, settings.max_decompressed_bytes)
    session.scan_img, session.scan, session.metadata = image, data, metadata
    session.scan_name, session.synthetic = file.filename, False
    session.mask_img = session.mask = None
    session.labels = []
    session.label_names = {}
    return scan_payload(session)


@app.post("/api/sessions/{session_id}/mask")
async def upload_mask(session_id: str, kind: Literal["reference", "annotation", "prediction"] = Form(...), file: UploadFile = File(...)) -> dict:
    session = require_scan(session_id)
    suffix = ".nii.gz" if (file.filename or "").lower().endswith(".nii.gz") else ".nii"
    target = session.directory / f"mask{suffix}"
    await save_upload(file, target)
    image, data, _metadata = load_nifti(target, settings.max_decompressed_bytes)
    labels = validate_mask(session.scan_img, session.scan, image, data)
    session.mask_img, session.mask = image, np.rint(data).astype(np.int32)
    session.mask_name, session.mask_kind, session.labels = file.filename, kind, labels
    session.label_names = {}
    return mask_payload(session)


@app.post("/api/sessions/{session_id}/inference", status_code=202)
async def submit_inference(session_id: str, t1c: UploadFile = File(...), t1: UploadFile = File(...),
                           t2: UploadFile = File(...), flair: UploadFile = File(...)) -> dict:
    try: session = store.get(session_id)
    except KeyError: fail(404, "Session not found.")
    paths = {}
    try:
        for name, upload in (("t1c", t1c), ("t1", t1), ("t2", t2), ("flair", flair)):
            suffix = ".nii.gz" if (upload.filename or "").lower().endswith(".nii.gz") else ".nii"
            path = session.directory / f"remote-{name}{suffix}"; await save_upload(upload, path); paths[name] = path
        loaded = {name: load_nifti(path, settings.max_decompressed_bytes) for name, path in paths.items()}
        reference = loaded["t1c"][0]
        for name in remote_inference.SEQUENCES:
            image, data, metadata = loaded[name]
            if not np.isfinite(data).all(): fail(422, f"{name}: all voxels must be finite.")
            if metadata.units != "mm": fail(422, f"{name}: spatial units must be millimetres.")
            if not np.allclose(metadata.spacing, (1, 1, 1), rtol=0, atol=1e-3): fail(422, f"{name}: model requires 1 mm spacing.")
            if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, rtol=1e-5, atol=1e-4):
                fail(422, f"{name}: geometry does not match T1c; automatic registration is disabled.")
        response = await remote_inference.submit(paths)
        session.remote_job_id = response["job_id"]
        return response
    except remote_inference.RemoteInferenceError as exc:
        fail(502, str(exc))


@app.get("/api/sessions/{session_id}/inference")
async def get_inference(session_id: str) -> dict:
    try: session = store.get(session_id)
    except KeyError: fail(404, "Session not found.")
    if not session.remote_job_id: fail(409, "No remote inference job exists for this session.")
    try:
        state = await remote_inference.status(session.remote_job_id)
        if state.get("status") != "completed": return state
        t1c = next((session.directory / name for name in ("remote-t1c.nii.gz", "remote-t1c.nii") if (session.directory / name).is_file()), None)
        if not t1c: fail(410, "The local T1c input is no longer available for result verification.")
        scan_img, scan, metadata, mask_img, mask, labels, provenance = await remote_inference.download_and_validate(
            session.remote_job_id, session.directory, t1c, settings.max_decompressed_bytes)
        session.scan_img, session.scan, session.metadata = scan_img, scan, metadata
        session.scan_name, session.synthetic = "T1c · remote inference reference", False
        session.mask_img, session.mask, session.labels = mask_img, mask, labels
        session.mask_name, session.mask_kind = "Remote MONAI prediction · imported", "prediction"
        session.label_names = {1: "Non-enhancing tumour-core region", 2: "Whole-tumour-only region", 4: "Enhancing tumour"}
        return {**state, "scan": scan_payload(session), "mask": mask_payload(session),
                "provenance": {"model": provenance.get("model"), "hardware": provenance.get("hardware"),
                               "inference": provenance.get("inference")}}
    except remote_inference.RemoteInferenceError as exc:
        fail(502, str(exc))


@app.post("/api/sessions/{session_id}/synthetic")
def synthetic_sample(session_id: str) -> dict:
    try:
        session = store.get(session_id)
    except KeyError:
        fail(404, "Session not found.")
    shape = (128, 144, 112)
    grid = np.indices(shape, dtype=np.float32)
    center = np.asarray(shape, dtype=np.float32)[:, None, None, None] / 2
    scaled = (grid - center) / np.asarray([45, 55, 43], dtype=np.float32)[:, None, None, None]
    brain = np.exp(-np.sum(scaled**2, axis=0) * 2.1)
    anatomy = 0.7 + 0.18 * np.sin(grid[0] / 7) + 0.12 * np.cos(grid[1] / 9)
    data = (brain * anatomy * 900).astype(np.float32)
    lesion1 = ((grid[0] - 78) / 13) ** 2 + ((grid[1] - 73) / 16) ** 2 + ((grid[2] - 62) / 11) ** 2 < 1
    lesion2 = ((grid[0] - 78) / 7) ** 2 + ((grid[1] - 73) / 9) ** 2 + ((grid[2] - 62) / 6) ** 2 < 1
    mask = np.zeros(shape, dtype=np.int16)
    mask[lesion1] = 1
    mask[lesion2] = 2
    affine = np.diag([1.0, 1.0, 1.2, 1.0])
    scan_img, mask_img = nib.Nifti1Image(data, affine), nib.Nifti1Image(mask, affine)
    scan_img.header.set_xyzt_units("mm")
    mask_img.header.set_xyzt_units("mm")
    scan_path, mask_path = session.directory / "synthetic_scan.nii.gz", session.directory / "synthetic_mask.nii.gz"
    nib.save(scan_img, scan_path)
    nib.save(mask_img, mask_path)
    scan_img, data, metadata = load_nifti(scan_path, settings.max_decompressed_bytes)
    mask_img, mask, _ = load_nifti(mask_path, settings.max_decompressed_bytes)
    session.scan_img, session.scan, session.metadata = scan_img, data, metadata
    session.scan_name, session.synthetic = "NeuroVista synthetic demonstration", True
    session.mask_img, session.mask = mask_img, mask.astype(np.int32)
    session.mask_name, session.mask_kind, session.labels = "Synthetic reference regions", "reference", [1, 2]
    session.label_names = {}
    return {"scan": scan_payload(session), "mask": mask_payload(session)}


def scan_payload(session: SessionData) -> dict:
    assert session.metadata is not None
    return {"session_id": session.id, "name": session.scan_name, "synthetic": session.synthetic,
            "metadata": session.metadata.as_dict(),
            "orientation_labels": {p: orientation_labels(session.metadata, p) for p in ("axial", "coronal", "sagittal")}}


def mask_payload(session: SessionData) -> dict:
    assert session.mask is not None and session.metadata is not None
    return {"name": session.mask_name, "kind": session.mask_kind, "labels": session.labels,
            "label_names": {str(label): session.label_names.get(label, f"Region {label}") for label in session.labels},
            "measurements": label_measurements(session.mask, np.asarray(session.metadata.affine), session.metadata.units)}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@app.post("/api/sessions/{session_id}/verified-demonstration")
def verified_demonstration(session_id: str) -> dict:
    """Open the preserved BRATS_457 technical demonstration without uploading it."""
    try:
        session = store.get(session_id)
    except KeyError:
        fail(404, "Session not found.")

    names = {
        "scan": "BRATS_457_t1c.nii.gz",
        "prediction": "neurovista_ai_prediction.nii.gz",
        "reference": "BRATS_457_reference.nii.gz",
        "provenance": "neurovista_ai_prediction_provenance.json",
        "comparison": "comparison.json",
    }
    paths = {key: settings.verified_demo_dir / name for key, name in names.items()}
    missing = [name for key, name in names.items() if not paths[key].is_file()]
    if missing:
        fail(404, f"Verified demonstration is unavailable. Missing from {settings.verified_demo_dir}: {', '.join(missing)}")

    try:
        provenance = json.loads(paths["provenance"].read_text(encoding="utf-8"))
        comparison = json.loads(paths["comparison"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        fail(422, f"Verified demonstration metadata could not be read: {exc}")

    expected_scan_hash = provenance.get("input_contract", {}).get("inputs", {}).get("t1c", {}).get("sha256")
    expected_prediction_hash = provenance.get("output", {}).get("sha256")
    expected_reference_hash = comparison.get("reference", {}).get("sha256")
    checks = (
        ("T1c scan", paths["scan"], expected_scan_hash),
        ("AI prediction", paths["prediction"], expected_prediction_hash),
        ("expert reference", paths["reference"], expected_reference_hash),
    )
    for label, path, expected in checks:
        if not expected or _sha256(path).lower() != str(expected).lower():
            fail(422, f"Verified demonstration {label} failed its recorded SHA-256 check.")

    scan_img, scan, metadata = load_nifti(paths["scan"], settings.max_decompressed_bytes)
    prediction_img, prediction, _ = load_nifti(paths["prediction"], settings.max_decompressed_bytes)
    reference_img, reference, _ = load_nifti(paths["reference"], settings.max_decompressed_bytes)
    prediction_labels = validate_mask(scan_img, scan, prediction_img, prediction)
    reference_labels = validate_mask(scan_img, scan, reference_img, reference)
    if not set(prediction_labels).issubset({1, 2, 4}):
        fail(422, f"Verified prediction has unsupported labels: {prediction_labels}")
    if not set(reference_labels).issubset({1, 2, 3}):
        fail(422, f"Verified reference has unsupported labels: {reference_labels}")

    regions = comparison.get("regions", {})
    required_regions = ("whole_tumour", "tumour_core", "enhancing_tumour")
    if any(regions.get(region, {}).get("status") != "calculated" for region in required_regions):
        fail(422, "Verified demonstration comparison is incomplete.")

    session.scan_img, session.scan, session.metadata = scan_img, scan, metadata
    session.scan_name, session.synthetic = "BRATS_457 T1c · verified local demonstration", False
    session.mask_img, session.mask = prediction_img, np.rint(prediction).astype(np.int32)
    session.mask_name, session.mask_kind, session.labels = "BRATS_457 AI prediction · imported", "prediction", prediction_labels
    session.label_names = {
        1: "Non-enhancing tumour-core region",
        2: "Whole-tumour-only region",
        4: "Enhancing tumour",
    }
    return {
        "scan": scan_payload(session),
        "mask": mask_payload(session),
        "demonstration": {
            "case": "BRATS_457",
            "scope": "single-case technical demonstration",
            "reference_verified": True,
            "reference_labels": reference_labels,
            "dice": {region: regions[region]["dice"] for region in required_regions},
            "independent_validation": bool(comparison.get("independent_validation", False)),
            "limitation": comparison.get("independence_note", "Possible training-subject overlap has not been ruled out."),
            "gpu": provenance.get("hardware", {}).get("gpu"),
            "inference_seconds": provenance.get("inference", {}).get("elapsed_seconds"),
            "peak_gpu_memory_gib": provenance.get("inference", {}).get("peak_gpu_memory_gib"),
        },
    }


@app.get("/api/sessions/{session_id}/slice/{plane}/{index}")
def get_slice(session_id: str, plane: Literal["axial", "coronal", "sagittal"], index: int,
              window: float = Query(..., gt=0), level: float = Query(...), opacity: float = Query(0.5, ge=0, le=1),
              labels: str = Query("")) -> Response:
    session = require_scan(session_id)
    selected = {int(v) for v in labels.split(",") if v.strip().isdigit()}
    image = render_slice(session.scan, session.mask, plane, index, window, level, opacity, selected)
    buffer = BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return Response(buffer.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/sessions/{session_id}/mesh/{label}")
def get_mesh(session_id: str, label: int) -> dict:
    session = require_scan(session_id)
    if session.mask is None:
        fail(409, "Upload a compatible segmentation mask first.")
    if label not in session.labels:
        fail(404, "Mask label not found.")
    return label_mesh(session.mask, label, session.metadata.spacing)


@app.get("/api/sessions/{session_id}/mask/foreground-centre")
def foreground_centre(session_id: str, label: int | None = Query(None, ge=1)) -> dict:
    session = require_scan(session_id)
    if session.mask is None:
        fail(409, "Upload a compatible segmentation mask first.")
    if label is not None and label not in session.labels:
        fail(404, "Mask label not found.")
    foreground = session.mask == label if label is not None else session.mask > 0
    coordinates = np.argwhere(foreground)
    if not len(coordinates):
        fail(422, "The selected mask region is empty.")
    centroid = coordinates.mean(axis=0)
    nearest = coordinates[np.argmin(np.sum((coordinates - centroid) ** 2, axis=1))]
    return {"voxel": [int(value) for value in nearest], "label": label}


@app.get("/api/sessions/{session_id}/export")
def export_results(session_id: str) -> Response:
    session = require_scan(session_id)
    payload = {
        "application": "NeuroVista", "application_version": app.version,
        "notice": "Research and education only — not for clinical diagnosis",
        "processing": {"location": "local FastAPI service", "resampling": False, "ai_model": None},
        "scan": scan_payload(session), "mask": mask_payload(session) if session.mask is not None else None,
    }
    return Response(json.dumps(payload, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="neurovista-results.json"'})


@app.get("/api/ai/status")
def ai_status() -> dict:
    return {"connected": False, "status": "AI model not connected", "device": None,
            "reason": "Stage 1 is active. Compatible weights and the four required MRI sequences have not been configured."}


# A production frontend build can be served by the same localhost-only process.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


