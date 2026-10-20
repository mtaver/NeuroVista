from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import httpx
import nibabel as nib
import numpy as np

from .config import settings
from .imaging import ImagingError, load_nifti, validate_mask

SEQUENCES = ("t1c", "t1", "t2", "flair")


class RemoteInferenceError(RuntimeError):
    pass


def configured() -> bool:
    if not settings.inference_url or not settings.inference_token:
        return False
    if settings.inference_url.startswith("https://"):
        return True
    return settings.inference_url.startswith(("http://127.0.0.1", "http://localhost"))


def require_configured() -> None:
    if not settings.inference_url or not settings.inference_token:
        raise RemoteInferenceError("Remote inference is not configured on this local backend.")
    if not configured():
        raise RemoteInferenceError("Remote inference URL must use HTTPS; plain HTTP is allowed only for localhost testing.")


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.inference_token}"}


def detail(response: httpx.Response) -> str:
    try: return str(response.json().get("detail", response.reason_phrase))
    except Exception: return response.reason_phrase


async def availability() -> dict:
    if not configured():
        return {"configured": False, "available": False, "status": "not_configured",
                "message": "Configure an HTTPS inference service URL and backend-only credential."}
    try:
        async with httpx.AsyncClient(timeout=settings.inference_connect_timeout_seconds) as client:
            response = await client.get(f"{settings.inference_url}/health")
        response.raise_for_status()
        payload = response.json()
        return {"configured": True, "available": True, "status": "available",
                "message": f"{payload.get('model', 'GPU model')} {payload.get('model_version', '')} is reachable.",
                "model": payload.get("model"), "model_version": payload.get("model_version")}
    except Exception as exc:
        return {"configured": True, "available": False, "status": "unavailable",
                "message": f"Remote inference service is unreachable: {type(exc).__name__}."}


async def submit(paths: dict[str, Path]) -> dict:
    require_configured()
    files = {}
    streams = []
    try:
        for name in SEQUENCES:
            stream = paths[name].open("rb"); streams.append(stream)
            files[name] = (paths[name].name, stream, "application/octet-stream")
        timeout = httpx.Timeout(settings.inference_transfer_timeout_seconds, connect=settings.inference_connect_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{settings.inference_url}/v1/jobs", headers=headers(), files=files)
        if response.status_code != 202:
            raise RemoteInferenceError(f"Remote submission failed ({response.status_code}): {detail(response)}")
        return response.json()
    except httpx.HTTPError as exc:
        raise RemoteInferenceError(f"Could not transfer the case to the inference service: {type(exc).__name__}.") from exc
    finally:
        for stream in streams: stream.close()


async def status(job_id: str) -> dict:
    require_configured()
    try:
        async with httpx.AsyncClient(timeout=settings.inference_connect_timeout_seconds) as client:
            response = await client.get(f"{settings.inference_url}/v1/jobs/{job_id}", headers=headers())
        if response.status_code != 200:
            raise RemoteInferenceError(f"Could not read remote job status ({response.status_code}): {detail(response)}")
        return response.json()
    except httpx.HTTPError as exc:
        raise RemoteInferenceError(f"Remote job status is unavailable: {type(exc).__name__}.") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


async def download_and_validate(job_id: str, directory: Path, t1c: Path, max_decompressed_bytes: int):
    require_configured(); package = directory / "remote-result.zip"; extracted = directory / "remote-result"
    try:
        timeout = httpx.Timeout(settings.inference_transfer_timeout_seconds, connect=settings.inference_connect_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("GET", f"{settings.inference_url}/v1/jobs/{job_id}/result", headers=headers()) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise RemoteInferenceError(f"Result download failed ({response.status_code}): {body[:200].decode(errors='replace')}")
                size = 0
                with package.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > settings.max_upload_bytes: raise RemoteInferenceError("Remote result exceeds the local download limit.")
                        output.write(chunk)
    except httpx.HTTPError as exc:
        raise RemoteInferenceError(f"Remote result transfer failed: {type(exc).__name__}.") from exc
    extracted.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(package) as archive:
            expected = {"neurovista_ai_prediction.nii.gz", "neurovista_ai_prediction_provenance.json"}
            names = set(archive.namelist())
            if names != expected or any(Path(name).name != name for name in names):
                raise RemoteInferenceError("Remote result package has unexpected or unsafe contents.")
            for name in expected:
                with archive.open(name) as source, (extracted / name).open("wb") as output: shutil.copyfileobj(source, output)
        provenance = json.loads((extracted / "neurovista_ai_prediction_provenance.json").read_text(encoding="utf-8"))
        expected_t1c = provenance["input_contract"]["inputs"]["t1c"]["sha256"]
        prediction_path = extracted / "neurovista_ai_prediction.nii.gz"
        if sha256_file(t1c) != expected_t1c: raise RemoteInferenceError("Result provenance does not match the submitted T1c scan.")
        if sha256_file(prediction_path) != provenance["output"]["sha256"]: raise RemoteInferenceError("Prediction checksum does not match its provenance.")
        scan_img, scan, metadata = load_nifti(t1c, max_decompressed_bytes)
        mask_img, mask, _ = load_nifti(prediction_path, max_decompressed_bytes)
        labels = validate_mask(scan_img, scan, mask_img, mask)
        if not set(labels).issubset({1, 2, 4}): raise RemoteInferenceError(f"Prediction contains unsupported labels: {labels}")
        return scan_img, scan, metadata, mask_img, np.rint(mask).astype(np.int32), labels, provenance
    except (KeyError, OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile, ImagingError) as exc:
        if isinstance(exc, RemoteInferenceError): raise
        raise RemoteInferenceError(f"Remote result validation failed: {exc}") from exc

