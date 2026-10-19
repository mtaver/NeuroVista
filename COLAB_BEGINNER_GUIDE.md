# Running the NeuroVista MONAI notebook in Google Colab

## What this workflow is

The notebook runs MONAI `brats_mri_segmentation` v0.5.4 in a user-controlled Google Colab session and downloads files for NeuroVista. It does not connect Colab to the local application.

- Local application status: **Local inference not connected**.
- After importing a downloaded mask: **Cloud-generated AI prediction imported**.
- Uploading data to Colab sends the selected files to Google's cloud environment. Use only de-identified research data you are authorized to process there.
- The output is research-only and is not a diagnosis.

The notebook's architecture, channel order, normalization, inference window, activation, threshold and label conversion match the v0.5.4 release. The refactored notebook has passed local JSON and Python syntax checks, but it has **not yet been rerun end-to-end on a GPU**. The earlier BRATS_457 notebook run remains the only completed GPU run recorded by this project.

## Model and environments

The model uses SegResNet with four inputs in this exact order: **T1c, T1, T2, FLAIR**. It uses nonzero channel-wise normalization, a `240 × 240 × 160` sliding window, batch size 1, overlap 0.5, sigmoid activation and threshold 0.5. Output precedence is enhancing tumour→4, otherwise tumour core→1, otherwise whole-tumour-only→2, otherwise background→0.

The two environments are recorded separately:

| Environment | Important versions |
|---|---|
| Original v0.5.4 metadata | PyTorch 2.4.0, MONAI 1.4.0, NumPy 1.24.4, NiBabel 5.2.1 |
| Adapted Colab Python 3.12 | PyTorch 2.4.0, MONAI 1.4.0, NumPy 1.26.4, NiBabel 5.2.1, torchvision 0.19.0, torchaudio 2.4.0 |

NumPy 1.24.4 is incompatible with Python 3.12. The adaptation changes NumPy to 1.26.4 but does not change the model architecture, weights or inference behavior.

## Before opening Colab

Choose one input path:

1. **Official MSD demonstration case** — the notebook downloads Medical Segmentation Decathlon Task01 BrainTumour and prepares BRATS_457 automatically.
2. **User-supplied research case** — supply four already co-registered, 1 mm isotropic NIfTI volumes from the same de-identified case.

The official MSD archive is approximately **7.61 GB to download**, even though only BRATS_457 is extracted. Its published MD5 is `240a19d752f0d9e9101544901065d872`. The dataset metadata identifies source order `0=FLAIR`, `1=T1`, `2=T1c/T1gd`, `3=T2` and licence **CC BY-SA 4.0**. A verified cached archive is reused instead of downloaded again.

## Exact execution steps

### 1. Open the notebook

1. Go to `https://colab.research.google.com/`.
2. Select **File → Upload notebook**.
3. Choose `notebooks/NeuroVista_MONAI_BraTS_Colab.ipynb` from this repository.

Uploading the notebook does not upload MRI data.

### 2. Select a GPU runtime

Choose **Runtime → Change runtime type → Hardware accelerator → GPU**, then save. Free GPU availability and GPU model are controlled by Colab. This guide does not require purchasing or provisioning a paid resource.

Run Stage 1. Expected output includes:

- Python `3.12.x`;
- the current process ID;
- available `/content` disk space.

If Python is not 3.12, start a fresh compatible runtime. If the official dataset path will be used, ensure at least 9 GiB is free.

### 3. Install, then restart exactly once

Run Stage 2 once. It installs the pinned CUDA 12.1 PyTorch family and the adapted Python 3.12 packages. Both installation commands use failure checking, so `INSTALLATION SUCCEEDED` appears only if both commands succeed.

When it succeeds:

1. Choose **Runtime → Restart session**.
2. Do not rerun Stage 2.
3. Continue with Stage 3.

Stage 3 compares the current process with the installer process. If you forgot to restart, it stops and tells you to restart. Expected successful output lists the original environment, adapted environment, RAM, GPU, VRAM and CUDA build. Continue only if `cuda_available` is true.

### 4. Download verified model weights

Run Stage 4. Expected output includes:

- model version `0.5.4`;
- source `MONAI/brats_mri_segmentation`;
- SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`;
- the cache path.

The weight is reused from cache and verified every time. A checksum mismatch stops the workflow.

### 5. Choose exactly one data path

In Stage 5, set `DATA_SOURCE` to either `msd_demo` or `upload`. Do not run both preparation cells.

#### Official BRATS_457 path

Leave `DATA_SOURCE='msd_demo'` and run Stage 5A.

The cell:

1. checks free disk space;
2. reuses a valid cached archive or downloads it once with progress;
3. verifies the official MD5;
4. safely extracts only the BRATS_457 4D image, expert mask and `dataset.json`;
5. splits the source channels into compressed `BRATS_457_flair.nii.gz`, `BRATS_457_t1.nii.gz`, `BRATS_457_t1c.nii.gz` and `BRATS_457_t2.nii.gz`;
6. creates `INPUTS` in the model's T1c, T1, T2, FLAIR order;
7. records MSD attribution and CC BY-SA 4.0.

Expected output prints the four exact input paths, reference-mask path, attribution and whether the archive cache was reused.

#### User-supplied path

Set `DATA_SOURCE='upload'`. Fill all four `USER_INPUT_NAMES` and the dataset/source/licence attribution fields. If an expert mask is available, set `USER_REFERENCE_NAME` to its filename. Set `ALLOW_USER_T1C_REDISTRIBUTION_IN_PACKAGE=True` only if you are authorized to include the scan and optional reference in the downloaded ZIP.

Run Stage 5B and select only the de-identified research volumes. It refuses missing names and never replaces a prepared MSD selection with placeholder paths.

### 6. Validate and preprocess

Run Stage 6. It verifies every path, dimensionality, numeric/finite data, affine, 1 mm isotropic spacing, millimetre units, matching shape and matching affine. It does not silently align incompatible scans.

Expected output includes:

- `model_channel_order`: `t1c`, `t1`, `t2`, `flair`;
- tensor shape `[1, 4, X, Y, Z]`;
- per-input checksums and geometry.

Any rejection means the inputs must be corrected before inference.

### 7. Run inference

Run Stage 7. This is the actual GPU execution. Expected output includes:

- `inference_complete: true`;
- elapsed seconds;
- peak allocated GPU memory;
- foreground voxel counts for TC, WT and ET.

If this cell fails or the session restarts, no valid in-memory result exists. Rerun the required prior stages; later cells deliberately refuse to fabricate or reconstruct a prediction.

### 8. Export prediction and provenance

Run Stage 8 only after Stage 7 succeeds. Expected output identifies:

- `neurovista_ai_prediction.nii.gz`;
- prediction SHA-256;
- `neurovista_ai_prediction_provenance.json`;
- `geometry_verified: true`.

The provenance records original and adapted environments separately, hardware, input hashes, preprocessing, release-exact inference settings, timing, memory, output labels, dataset attribution and limitations.

### 9. Optionally compare with the reference

Run Stage 9. For the MSD path, it validates reference/prediction geometry and labels before computing whole-tumour, tumour-core and enhancing-tumour Dice. Both-empty regions are reported as not applicable; exactly one empty returns Dice 0.

For user uploads without a reference, the cell prints that comparison was skipped and creates no metrics. It never infers a reference or invents results.

Any comparison is one case only. It is not diagnostic accuracy or independent validation. For BRATS_457, possible overlap with the model's reported BraTS-derived training subjects remains unresolved.

### 10. Package and download

Run Stage 10. The ZIP contains:

- `neurovista_ai_prediction.nii.gz`;
- `neurovista_ai_prediction_provenance.json`;
- `DATASET_ATTRIBUTION.json`;
- matching T1c `.nii.gz` when redistribution is permitted;
- expert reference `.nii.gz` when present and redistribution is permitted;
- `expert_comparison.json` when calculated;
- `README_IMPORT.txt`.

NIfTI files remain compressed. Official MSD files carry dataset attribution and CC BY-SA 4.0 information. User-supplied T1c/reference files are omitted unless redistribution permission is explicitly confirmed.

Wait for the browser download, then open the ZIP on your computer and confirm its contents before cleanup.

### 11. Import locally

1. Start the local NeuroVista backend and frontend using the repository README.
2. Load the matching T1c scan.
3. Choose **AI prediction import**.
4. Import `neurovista_ai_prediction.nii.gz`.
5. Confirm the UI says **Local inference not connected** and **Cloud-generated AI prediction imported**.
6. Keep the provenance and attribution JSON beside the mask.

Importing a file does not create a live Colab connection and does not run inference locally.

### 12. Clean up

Only after the ZIP opens locally, set `DOWNLOAD_CONFIRMED=True` in Stage 11 and run it. Leave `DELETE_VERIFIED_CACHE_TOO=False` if you may need to repackage during this session; this prevents an unnecessary repeated 7.61 GB download. Set it true only when you intentionally want to remove the verified cache.

Finally choose **Runtime → Disconnect and delete runtime**. Runtime deletion does not guarantee immediate provider-level erasure; Google's current retention policy applies.

## Completed milestone and remaining verification

The earlier BRATS_457 run completed on a Tesla T4 in 1.488733485 seconds with 2.760735 GiB peak allocated GPU memory. Its local comparison produced Dice 0.896640 whole tumour, 0.834695 tumour core and 0.831881 enhancing tumour. This is a single-case demonstration, not diagnostic accuracy or independent validation; possible training-subject overlap is unresolved.

The refactored notebook still needs one fresh end-to-end Colab GPU run to verify its new control flow, download, packaging and cleanup stages. Local syntax and repository tests do not substitute for that cloud execution.
