from pathlib import Path

import httpx
import pytest

import app.remote_inference as remote

RealAsyncClient = httpx.AsyncClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


class MockClient:
    def __init__(self, transport, **_kwargs): self.client = RealAsyncClient(transport=transport)
    async def __aenter__(self): return self.client
    async def __aexit__(self, *args): await self.client.aclose()


@pytest.mark.anyio
async def test_mocked_availability_reports_release(monkeypatch):
    monkeypatch.setattr(remote, "settings", __import__('dataclasses').replace(remote.settings, inference_url="https://gpu.example", inference_token="test-token"))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"model": "MONAI brats_mri_segmentation", "model_version": "0.5.4"}))
    monkeypatch.setattr(remote.httpx, "AsyncClient", lambda **kwargs: MockClient(transport, **kwargs))
    result = await remote.availability()
    assert result["available"] is True
    assert result["model_version"] == "0.5.4"


@pytest.mark.anyio
async def test_mocked_submission_keeps_bearer_token_on_backend(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "settings", __import__('dataclasses').replace(remote.settings, inference_url="https://gpu.example", inference_token="backend-secret"))
    paths = {}
    for name in remote.SEQUENCES:
        path = tmp_path / f"{name}.nii.gz"; path.write_bytes(b"test"); paths[name] = path
    def handler(request):
        assert request.headers["Authorization"] == "Bearer backend-secret"
        return httpx.Response(202, json={"job_id": "mock-job", "status": "queued"})
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(remote.httpx, "AsyncClient", lambda **kwargs: MockClient(transport, **kwargs))
    result = await remote.submit(paths)
    assert result == {"job_id": "mock-job", "status": "queued"}


def test_remote_plain_http_rejected(monkeypatch):
    monkeypatch.setattr(remote, "settings", __import__('dataclasses').replace(remote.settings, inference_url="http://gpu.example", inference_token="secret"))
    with pytest.raises(remote.RemoteInferenceError, match="HTTPS"):
        remote.require_configured()
