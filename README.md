# NeuroVista

NeuroVista is a local-first research and education workspace for inspecting 3D NIfTI brain MRI volumes and compatible segmentation masks. It is **not a medical device and not for clinical diagnosis**.

## What works now

- `.nii` and `.nii.gz` scan upload with compressed and decompressed size limits
- linked axial, coronal, and sagittal views with physical aspect ratios
- orientation labels derived from the NIfTI affine
- slice, window, level, zoom, and reset controls
- reference-mask or user-annotation upload with strict dimension, affine, and label validation
- label overlays, opacity and per-region visibility controls
- region volume in mL calculated from the affine determinant when spatial units are known
- interactive 3D mask surfaces
- local temporary sessions, clear-session control, and JSON research export
- bundled synthetic workflow labelled **“Synthetic demonstration — not a patient scan”**

AI segmentation is intentionally disabled in Stage 1. The UI reports **“AI model not connected”** and does not generate fake predictions.

## Windows prerequisites

- Python 3.11 or 3.12, 64-bit
- Node.js 20 LTS or newer, including npm
- Git

This project is designed to work on CPU. Slice viewing and mask surfaces do not need a GPU. Future MONAI inference will be much slower on CPU and will require substantially more RAM; no GPU is assumed or reported unless PyTorch detects it at runtime.

## Setup in PowerShell

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements-dev.txt

Set-Location frontend
npm install
Set-Location ..
```

If PowerShell blocks activation for this one session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run in development

Open two PowerShell terminals in the repository root.

Backend:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
Set-Location frontend
npm run dev
```

Open `http://127.0.0.1:5173`. The development server proxies `/api` requests to FastAPI.

## Production-style local run

```powershell
Set-Location frontend
npm run build
Set-Location ..
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. FastAPI serves `frontend/dist` when it exists.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "backend"
pytest backend\tests -q
Set-Location frontend
npm run build
```

## Privacy and retention

The services bind to `127.0.0.1` by default. Uploaded scans are streamed into a randomly named directory under the operating-system temporary directory. They are never sent to a third party. Use **Clear session** to delete the active session immediately. Temporary files may otherwise remain until the process or operating-system cleanup removes them; do not rely on this application as a long-term data store.

Uploads, datasets, weights, credentials, and common patient-data file extensions are excluded from Git. Do not place identifiable patient data in the source tree.

## Project structure

```text
backend/app/       FastAPI service and imaging logic
backend/tests/     geometry, volume, orientation, and upload tests
frontend/src/      React/TypeScript workspace
DATA_SOURCES.md    official sample-data acquisition and licensing
MODEL_CARD.md      planned model integration facts and blockers
CLOUD_INFERENCE.md assessed local-viewer/cloud-GPU workflow (not provisioned)
IMPLEMENTATION_STATUS.md verified scope and limitations
```

## Data and model setup

See [DATA_SOURCES.md](DATA_SOURCES.md) for the official Medical Segmentation Decathlon source. Do not commit downloaded MRI archives. See [MODEL_CARD.md](MODEL_CARD.md) for the researched MONAI bundle; model execution remains a Stage 2 task.

See [CLOUD_INFERENCE.md](CLOUD_INFERENCE.md) for a privacy-gated cloud-GPU design assessment. It does not enable inference or authorize upload of scan data.

