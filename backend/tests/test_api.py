from io import BytesIO
from dataclasses import replace
import hashlib
import json

from fastapi import HTTPException, UploadFile
import nibabel as nib
import numpy as np
import pytest

from typing import get_args, get_origin, get_type_hints

import app.main as main_module
from app.main import get_slice, new_session, synthetic_sample, upload_mask, upload_scan, verified_demonstration


def test_invalid_upload_extension():
    session = new_session()["session_id"]
    upload = UploadFile(filename="bad.txt", file=BytesIO(b"not a nifti"))
    with pytest.raises(HTTPException) as exc:
        upload_scan(session, upload).send(None)
    assert exc.value.status_code == 415


def test_synthetic_main_workflow():
    session = new_session()["session_id"]
    body = synthetic_sample(session)
    assert body["scan"]["synthetic"] is True
    assert body["mask"]["kind"] == "reference"
    response = get_slice(session, "axial", 56, window=900, level=450, opacity=0.5, labels="1,2")
    assert response.status_code == 200
    assert response.media_type == "image/png"
    assert len(response.body) > 100


def test_prediction_provenance_is_accepted_for_compatible_mask():
    annotation = get_type_hints(upload_mask)["kind"]
    assert get_origin(annotation) is not None
    assert "prediction" in get_args(annotation)


def test_verified_demonstration_reports_missing_files(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "settings", replace(main_module.settings, verified_demo_dir=tmp_path))
    session = new_session()["session_id"]
    with pytest.raises(HTTPException) as exc:
        verified_demonstration(session)
    assert exc.value.status_code == 404
    assert "BRATS_457_t1c.nii.gz" in exc.value.detail


def test_verified_demonstration_checks_and_loads_all_artifacts(tmp_path, monkeypatch):
    affine = np.eye(4)
    scan = np.arange(4 * 5 * 6, dtype=np.float32).reshape((4, 5, 6))
    prediction = np.zeros(scan.shape, dtype=np.int16)
    prediction[1:3, 1:4, 1:5] = 2
    prediction[2, 2, 2] = 4
    reference = np.zeros(scan.shape, dtype=np.int16)
    reference[1:3, 1:4, 1:5] = 1
    reference[2, 2, 2] = 3
    files = {
        "scan": tmp_path / "BRATS_457_t1c.nii.gz",
        "prediction": tmp_path / "neurovista_ai_prediction.nii.gz",
        "reference": tmp_path / "BRATS_457_reference.nii.gz",
    }
    for data, path in ((scan, files["scan"]), (prediction, files["prediction"]), (reference, files["reference"])):
        image = nib.Nifti1Image(data, affine)
        image.header.set_xyzt_units("mm")
        nib.save(image, path)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    (tmp_path / "neurovista_ai_prediction_provenance.json").write_text(json.dumps({
        "input_contract": {"inputs": {"t1c": {"sha256": sha(files["scan"])}}},
        "output": {"sha256": sha(files["prediction"])},
        "hardware": {"gpu": "Tesla T4"},
        "inference": {"elapsed_seconds": 1.488733485, "peak_gpu_memory_gib": 2.760735},
    }), encoding="utf-8")
    (tmp_path / "comparison.json").write_text(json.dumps({
        "reference": {"sha256": sha(files["reference"])},
        "independent_validation": False,
        "independence_note": "Possible training-subject overlap remains unresolved.",
        "regions": {
            "whole_tumour": {"status": "calculated", "dice": 0.896640},
            "tumour_core": {"status": "calculated", "dice": 0.834695},
            "enhancing_tumour": {"status": "calculated", "dice": 0.831881},
        },
    }), encoding="utf-8")
    monkeypatch.setattr(main_module, "settings", replace(main_module.settings, verified_demo_dir=tmp_path))

    session = new_session()["session_id"]
    body = verified_demonstration(session)
    assert body["scan"]["name"].startswith("BRATS_457 T1c")
    assert body["mask"]["kind"] == "prediction"
    assert body["demonstration"]["reference_verified"] is True
    assert body["demonstration"]["independent_validation"] is False
    assert body["demonstration"]["dice"]["whole_tumour"] == pytest.approx(0.896640)

