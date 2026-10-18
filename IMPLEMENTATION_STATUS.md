# Implementation status

Last updated: 2026-10-18

## Stage 1 — implemented

- Local FastAPI and React/TypeScript application structure
- NIfTI `.nii`/`.nii.gz` upload with extension, compressed-size, decompressed-size, dimension, affine, and finite-data checks
- Linked axial, coronal, and sagittal navigation
- Anatomical edge labels derived from affine axis codes
- Display aspect ratios derived from voxel spacing
- Window, level, zoom, slice, and reset controls
- Scan dimensions, voxel spacing, spatial units, orientation, and datatype display
- Reference-mask and user-annotation provenance choices
- Strict mask shape, affine, finite-value, integer-label, nonnegative-label, and label-count checks
- Coloured overlays, legend, opacity, and label visibility
- Per-label volumes in mL derived from `abs(det(affine[:3,:3]))` and verified spatial units
- Interactive rotate/zoom 3D surfaces with region visibility controls
- Empty, loading, validation-error, and mesh-error states
- Local JSON export with scan/mask measurements and processing provenance
- Clear-session operation and local temporary-file processing
- Deterministic synthetic demonstration with an explicit non-patient label
- Tests for volume conversion, dimension mismatch, affine mismatch, invalid fractional labels, orientation mapping, invalid upload type, and the synthetic scan/mask/slice workflow

## Stage 1 — verified

- Python 3.12 virtual environment created and pinned backend/development dependencies installed
- Backend test suite: **8 passed** (`pytest backend\\tests -q`)
- Frontend TypeScript check and Vite production build: **passed** (`npm run build`)
- Local FastAPI startup and `/api/health`: **passed** on `127.0.0.1:8000`
- Browser QA: initial/empty state, privacy notice, synthetic-sample loading state, loaded metadata, explicit synthetic provenance, mask provenance, region volumes, overlay rendering, linked view orientation/crosshairs, and 3D canvas initialization were observed
- Real-data QA with official MSD Task04 `hippocampus_001`: upload, reference-mask compatibility, RAS orientation, plane labels, overlay rendering, affine-derived volumes, and both 3D surfaces passed; detailed results are in `DATA_SOURCES.md`
- The hippocampus case validates viewer behavior only; it is not evidence of tumour segmentation or model performance

## Stage 1 — limitations

- Hardware inventory: 7.78 GiB physical RAM (0.98 GiB free during inspection), Intel UHD Graphics 620, no NVIDIA adapter, no `nvidia-smi`, and therefore no CUDA support detected.
- The UI uses one global zoom value and click-based linked crosshair movement; drag-to-pan is not implemented.
- NIfTI time series and non-singleton 4D inputs are rejected.
- Images are rendered server-side as PNG slices. This prioritizes safe parsing and consistent overlay geometry over high-frame-rate scrolling.
- Temporary-session cleanup is explicit. Automatic TTL cleanup is configured conceptually but not yet scheduled; operating-system temporary cleanup remains a fallback.
- The frontend uses local system fonts and makes no third-party browser requests.

## Stage 2 — preparation implemented; AI not connected

- Candidate: Project MONAI `brats_mri_segmentation` bundle v0.5.4; official 18.8 MB weight availability, SHA-256, Apache-2.0 licence, four-sequence channel order, preprocessing, inference window, and output mapping verified in `MODEL_CARD.md`
- Status shown by the app: **AI model not connected**
- No weights, predictions, confidence values, GPU state, performance, or processing-time claims are fabricated
- Blockers: only 7.78 GiB RAM with 0.98 GiB free at inspection, no CUDA-capable GPU, PyTorch/MONAI not installed, and no compatible co-registered T1c/T1/T2/FLAIR case available for real inference validation
- Stage 2 was not enabled because real compatible inference has not succeeded
- A separate local-viewer/cloud-GPU workflow is assessed in `CLOUD_INFERENCE.md`; no data was uploaded and no resource was provisioned
- Colab notebook prepared for real v0.5.4 inference with pinned dependencies, GPU/RAM checks, official weight checksum verification, four-sequence validation, documented preprocessing, original-geometry NIfTI/JSON export, download packaging, and cleanup instructions
- Local viewer accepts a geometrically compatible imported mask under the distinct provenance **AI prediction · imported**; reference masks and user annotations remain separate
- Localhost API verification passed for a geometrically compatible mask uploaded with `kind=prediction`; no data left the computer
- Notebook structure and all Python cells passed local JSON/AST validation; the official v0.5.4 weight download matched the documented SHA-256
- **GPU execution remains unverified** because the notebook has not been run with a compatible four-sequence case

## Stage 3 — planned, not implemented

Learning mode, hidden-reference submission, annotation comparison, and reviewed educational explanations will follow only after Stage 1 verification and Stage 2 decisions.

## Repository status

The local repository is on `main` and connected to `https://github.com/mtaver/NeuroVista.git`. Stage 1 was previously pushed without rewriting remote history. This Stage 2 preparation will also be committed and pushed normally, without force-pushing.

