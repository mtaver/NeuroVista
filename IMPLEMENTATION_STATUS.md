# Implementation status

Last updated: 2026-10-20

## Public static demonstration

- A separate browser-only GitHub Pages build presents the permitted CC BY-SA 4.0 MSD BRATS_457-derived display assets, precomputed AI overlay, region volumes, interactive 3D surfaces and recorded single-case Dice comparison.
- Public file selection is browser-local: 3D `.nii`/`.nii.gz` scans and compatible masks are parsed in volatile memory without a receiving endpoint, persistence, service credential, local path, `.tmp` file, published original NIfTI, or Python-backend dependency. Hosted inference remains disabled.
- The public viewer validates size, datatype, finite voxels, dimensions, supported spatial units and affine geometry; a mask requires an explicit source category before local volume and surface generation.
- Documentation identifies the public site as a static presentation of a previously generated result; hosted inference and uploads remain disabled.
- Dataset attribution, transformation notice, ShareAlike terms and possible training-subject-overlap limitation are displayed publicly.

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

## Stage 2 — cloud-file workflow verified; local inference not connected

- An authenticated portable Docker GPU worker and optional local-backend connection are implemented. No hosted service, paid resource or persistent endpoint has been created, and this new path has uploaded no scans. Real container GPU execution and the first authenticated HTTPS end-to-end run remain unverified; see `HOSTED_INFERENCE.md`.
- Candidate: Project MONAI `brats_mri_segmentation` bundle v0.5.4; official 18.8 MB weight availability, SHA-256, Apache-2.0 licence, four-sequence channel order, preprocessing, inference window, and output mapping verified in `MODEL_CARD.md`
- Status shown by the app: **Local inference not connected**; when applicable, **Cloud-generated AI prediction imported**
- No local model is installed and there is no live Colab connection
- The local computer still has no CUDA-capable GPU and does not provide local inference
- A separate local-viewer/cloud-GPU workflow is assessed in `CLOUD_INFERENCE.md`; the recorded BRATS_457 research case was uploaded by the user for the completed Colab run, but no persistent service or paid resource was provisioned
- Colab notebook prepared for real v0.5.4 inference with pinned dependencies, GPU/RAM checks, official weight checksum verification, four-sequence validation, documented preprocessing, original-geometry NIfTI/JSON export, download packaging, and cleanup instructions
- Local viewer accepts a geometrically compatible imported mask under the distinct provenance **AI prediction · imported**; reference masks and user annotations remain separate
- Localhost API verification passed for a geometrically compatible mask uploaded with `kind=prediction`; no data left the computer
- Notebook structure and all Python cells passed local JSON/AST validation; the official v0.5.4 weight download matched the documented SHA-256
- Beginner Colab guide added for official MSD Task01 `BRATS_457`, together with a locally verified helper that splits the dataset's documented FLAIR/T1/T1gd/T2 4D order into four aligned files without resampling
- Colab environment adapted for Python 3.12: NumPy 1.26.4 replaces the model metadata's incompatible 1.24.4 pin; the notebook records the distinction and rejects Python/package mismatches before inference
- A real Colab run completed for MSD Task01 `BRATS_457` on a Tesla T4 using MONAI model v0.5.4, PyTorch 2.4.0+cu121, MONAI 1.4.0 and NumPy 1.26.4; measured inference time was 1.488733485 seconds and peak allocated GPU memory was 2.760735 GiB
- The downloaded prediction and T1c hashes matched provenance; their `240 × 240 × 155` RAS, 1 mm geometry matched; labels 0/1/2/4 were accepted; overlays, volumes and all three 3D meshes rendered locally
- This is a completed cloud-to-local file workflow, not a live service connection and not evidence of prediction accuracy
- The matching MSD expert mask was compared after exact shape/affine and label validation. Single-case Dice was **0.896640 whole tumour**, **0.834695 tumour core**, and **0.831881 enhancing tumour**
- The observed run used a **Tesla T4**, completed model inference in **1.488733485 seconds**, and measured **2.760735 GiB** peak allocated GPU memory
- These figures are a **single-case technical demonstration**, not diagnostic accuracy, cohort performance, or independent validation; possible subject overlap between the model's reported BraTS 2018 source and the MSD BraTS 2016/2017-derived case remains unresolved
- The Colab notebook is refactored into prerequisite-checked stages with one explicit restart, complete post-restart initialization, mutually exclusive MSD/upload preparation, checksum-verified cache reuse, strict inference/export state, optional expert comparison, licence-aware result packaging, and confirmation-gated cleanup
- The local workspace now provides **Open verified demonstration** for the preserved ignored BRATS_457 artifacts. It refuses partial or altered sets, checks the recorded scan/prediction/reference SHA-256 values, validates both mask geometries and label sets, and opens the cloud-generated prediction with its single-case comparison and overlap warning
- Workspace refinement separates the active mask provenance from the next-upload source, provides verified MONAI/BraTS region names, equal linked MRI viewports, foreground-region navigation, and physical-coordinate-preserving 3D surfaces with fit/reset/anatomical/fullscreen cameras plus independent per-region visibility and opacity
- Foreground-region navigation now reports a visible success or actionable error, scrolls the linked MRI views into view, explains disabled states, and is browser-verified with mouse and keyboard activation after moving all three slices away from the selected foreground voxel

### Refactored-notebook fresh-run verification — blocked, not complete

GPU attempts are paused. The latest fresh-session verification is **blocked by Colab GPU unavailability** and must not be read as end-to-end verification of the refactored notebook.

Stages actually verified before the block:

- The Colab `2026.07` fallback runtime started with Python **3.12.13** after the failed Python 3.13 runtime was terminated
- The pinned Python 3.12 dependency installation completed, the one required session restart completed, and post-restart imports/version checks passed
- Verified runtime: PyTorch `2.4.0+cu121`, torchvision `0.19.0+cu121`, torchaudio `2.4.0+cu121`, MONAI `1.4.0`, NumPy `1.26.4`, nibabel `5.2.1`, Tesla T4 with CUDA available, 14.563 GiB VRAM, and 12.671 GiB total RAM
- Official MONAI bundle v0.5.4 weights downloaded and matched SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`
- The official MSD demonstration source was selected and data preparation was started

Not verified in that fresh run:

- completion of MSD case preparation
- inference
- expert-reference comparison
- packaging and download
- cleanup after confirmed download

On reconnection, Colab reported **“Failed to assign a backend — No backend with GPU available.”** The successful BRATS_457 metrics documented above belong to the earlier completed run and remain valid as a preserved single-case demonstration; they do not make the refactored fresh run complete.

## Stage 3 — planned, not implemented

Learning mode, hidden-reference submission, annotation comparison, and reviewed educational explanations will follow only after Stage 1 verification and Stage 2 decisions.

## Repository status

The local repository is on `main` and connected to `https://github.com/mtaver/NeuroVista.git`. Stage 1 was previously pushed without rewriting remote history. This Stage 2 preparation will also be committed and pushed normally, without force-pushing.

