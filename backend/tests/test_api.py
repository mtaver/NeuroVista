from io import BytesIO

from fastapi import HTTPException, UploadFile
import pytest

from app.main import get_slice, new_session, synthetic_sample, upload_scan


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

