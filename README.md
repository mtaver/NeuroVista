# NeuroVista

NeuroVista is a local-first research and education workspace for inspecting 3D NIfTI brain MRI volumes and compatible segmentation masks. It is **not a medical device and not for clinical diagnosis**.

## What works now

- `.nii` and `.nii.gz` scan upload with compressed and decompressed size limits
- linked axial, coronal, and sagittal views with physical aspect ratios
- orientation labels derived from the NIfTI affine
- slice, window, level, zoom, and reset controls
- reference-mask or user-annotation upload with strict dimension, affine, and label validation
- imported AI-prediction masks with visually distinct provenance labelling
- label overlays, opacity and per-region visibility controls
- region volume in mL calculated from the affine determinant when spatial units are known
- interactive 3D mask surfaces
- local temporary sessions, clear-session control, and JSON research export
- bundled synthetic workflow labelled **“Synthetic demonstration — not a patient scan”**
- one-click **Open verified demonstration** action for an intact, locally preserved BRATS_457 artifact set

Local AI inference remains disabled. The UI reports **“Local inference not connected”**. When a verified external result file is loaded it separately reports **“Cloud-generated AI prediction imported”**; this does not imply a live Colab connection.

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

### Windows double-click launcher

After completing setup once, double-click `Start-NeuroVista.cmd` in the project folder. The launcher:

- uses the existing `.venv` and `frontend/node_modules` environments
- reuses healthy services already listening on `127.0.0.1:8000` and `127.0.0.1:5173`
- starts only missing services and waits up to 60 seconds for their HTTP readiness checks
- opens `http://127.0.0.1:5173` only after both services are ready
- leaves the backend and frontend running after the launcher window closes
- writes timestamped process logs under the Git-ignored `.tmp/runtime-logs` directory

If an environment is missing, a service exits, readiness times out, or one of the localhost ports is occupied by an unhealthy process, the launcher shows an actionable error and pauses so it can be read. It does not modify firewall settings or expose either service beyond localhost.

For troubleshooting without opening a browser:

```powershell
.\Start-NeuroVista.ps1 -NoBrowser
```

The manual commands remain available below.

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
notebooks/         Colab preparation for real MONAI BraTS inference
IMPLEMENTATION_STATUS.md verified scope and limitations
```

## Data and model setup

See [DATA_SOURCES.md](DATA_SOURCES.md) for the official Medical Segmentation Decathlon source. Do not commit downloaded MRI archives. See [MODEL_CARD.md](MODEL_CARD.md) for the researched MONAI bundle; model execution remains a Stage 2 task.

See [CLOUD_INFERENCE.md](CLOUD_INFERENCE.md) for a privacy-gated cloud-GPU design assessment. It does not enable inference or authorize upload of scan data.

## Prepared Colab inference workflow

[NeuroVista_MONAI_BraTS_Colab.ipynb](notebooks/NeuroVista_MONAI_BraTS_Colab.ipynb) prepares a real, checksum-verified MONAI BraTS v0.5.4 inference run on an explicitly selected Google Colab GPU runtime. Opening or running the notebook is a separate cloud-processing decision: its upload cell transfers the selected T1c, T1, T2 and FLAIR files to Google Colab. Use only authorized, de-identified research data and review the notebook warnings first.

For a beginner-friendly walkthrough using an official MSD/BraTS tumour research case, including download verification, four-channel splitting, execution blockers, cleanup and local import, see [COLAB_BEGINNER_GUIDE.md](COLAB_BEGINNER_GUIDE.md).

One real GPU inference has completed for the single MSD Task01 `BRATS_457` case and its exported files passed local hash, label and geometry checks. The corresponding expert comparison produced Dice 0.896640 whole tumour, 0.834695 tumour core and 0.831881 enhancing tumour. See [BRATS_457_WORKFLOW.md](BRATS_457_WORKFLOW.md) for the measured run and limitations. This is a single-case demonstration, does not connect a model locally, and does not establish diagnostic accuracy or independent validation.

The refactored notebook's separate fresh-run verification is currently blocked because Colab could not assign another GPU backend. Installation, the required restart, post-restart initialization, runtime/GPU inspection and official-weight checksum verification passed before the block; data preparation through cleanup did not complete in that fresh run. GPU attempts are paused.

## Open the preserved verified demonstration

The **Open verified demonstration** button looks only in the ignored local directory `.tmp/prediction-import-BRATS_457`. It requires:

- `BRATS_457_t1c.nii.gz`
- `neurovista_ai_prediction.nii.gz`
- `BRATS_457_reference.nii.gz`
- `neurovista_ai_prediction_provenance.json`
- `comparison.json`

The backend checks the recorded scan, prediction and reference SHA-256 values, validates prediction and reference geometry/labels, then displays the prediction as **AI prediction · imported**. The expert reference is used to attest the recorded comparison; the active overlay remains the prediction. If a file is absent or fails validation, the UI reports the exact problem. These ignored local artifacts are never added to Git.

After a successful notebook run, extract `neurovista_prediction_package.zip`. In the local viewer:

1. Upload the exact T1c reference scan used by the notebook.
2. Select **AI prediction import** under mask provenance.
3. Upload `neurovista_ai_prediction.nii.gz`.
4. Keep and review `neurovista_ai_prediction_provenance.json`; the viewer validates mask geometry but does not independently attest that the cloud inference was valid.

