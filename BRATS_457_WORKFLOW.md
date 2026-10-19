# BRATS_457 Colab-to-local workflow record

## Status boundary

- **Local inference not connected.** NeuroVista has no local model or weights and does not invoke Colab.
- **Cloud-generated AI prediction imported.** A completed Colab result was downloaded as files, independently checked, and imported into the local viewer.
- There is no live Colab connection, remote endpoint, background synchronization or public deployment.

## Completed single-case workflow

The de-identified MSD Task01 `BRATS_457` T1c scan and the prediction package were received as local downloads on 2026-10-20. The ZIP was safely extracted under ignored `.tmp` storage without decompressing the inner `.nii.gz`. The downloaded originals were preserved.

The provenance and files reported:

- MONAI bundle `brats_mri_segmentation` v0.5.4
- weight SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`
- Python 3.12.13, PyTorch 2.4.0+cu121, MONAI 1.4.0, NumPy 1.26.4
- Tesla T4, 1.488733485 seconds measured inference time, 2.760735 GiB measured peak allocated GPU memory
- prediction SHA-256 `23b25b0af158127d090d226ff4a0a8d5192f0421fc01a04b1b09c9b1f9b90e07`
- T1c SHA-256 `7ee0a2b489be16bc750e3f35edcb3ef65a060f457d050c0f138ebd6900f7bd42`

Both file hashes matched the provenance. Scan, prediction and provenance geometry matched at `240 × 240 × 155`, 1 mm isotropic, RAS, with an identity affine. The prediction contained only supported values 0, 1, 2 and 4.

The local UI displayed **AI prediction · imported**, visible overlays, and affine-derived volumes:

| Prediction label | Voxels | Volume |
|---:|---:|---:|
| 1 | 488 | 0.488 mL |
| 2 | 80,472 | 80.472 mL |
| 4 | 2,980 | 2.980 mL |

All three surface requests succeeded: label 1 produced 2,056 vertices/4,180 faces; label 2 produced 24,954 vertices/50,040 faces; label 4 produced 2,190 vertices/4,376 faces. These results validate execution, transport, geometry, measurements, overlays and rendering—not medical accuracy.

## Completed expert-reference comparison

The corresponding MSD expert mask was downloaded separately, preserved, copied into ignored `.tmp` storage, and compared with the actual imported file `neurovista_ai_prediction.nii.gz`. The source and copied reference both had SHA-256 `ab30e8774ef7a679531eb95dec3adb8aa9aef0e109c0207eb4d435da184c4249`. Reference and prediction geometry matched at `240 × 240 × 155`, 1 mm isotropic, RAS, with an identity affine.

MSD Task01 defines reference labels as 0 background, 1 edema, 2 non-enhancing tumour and 3 enhancing tumour. The imported prediction uses 0 background, 1 tumour-core remainder, 2 whole-tumour-only remainder and 4 enhancing tumour.

Dice comparison therefore uses these composite regions:

| Region | MSD expert labels | Prediction labels |
|---|---|---|
| Whole tumour | 1, 2, 3 | 1, 2, 4 |
| Tumour core | 2, 3 | 1, 4 |
| Enhancing tumour | 3 | 4 |

`scripts/compare_brats_regions.py` rejected neither file: all observed labels were supported and geometry matched. If both masks are empty for a region, Dice is reported as `null` / not applicable. If exactly one is empty, Dice is 0. Otherwise Dice is `2 × intersection / (reference + prediction)`.

| Composite region | Reference voxels | Prediction voxels | Intersection | Dice |
|---|---:|---:|---:|---:|
| Whole tumour | 73,791 | 83,940 | 70,714 | **0.896640** |
| Tumour core | 3,265 | 3,468 | 2,810 | **0.834695** |
| Enhancing tumour | 3,218 | 2,980 | 2,578 | **0.831881** |

All three regions were non-empty, so the ordinary Dice formula applied. These values are a **single-case technical demonstration**. They are not diagnostic accuracy, a clinical-performance estimate, a cohort result, or independent validation.

After the reference mask is downloaded into ignored storage, run:

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_brats_regions.py `
  .\.tmp\prediction-import-BRATS_457\BRATS_457_reference.nii.gz `
  .\.tmp\prediction-import-BRATS_457\neurovista_ai_prediction.nii.gz `
  --output .\.tmp\prediction-import-BRATS_457\comparison.json
```

## Reproducing the comparison

The refactored notebook can optionally calculate the same comparison before packaging. For a prior runtime, this cell downloads only an already-extracted reference and never downloads the dataset archive again. If the runtime was reset or deleted, it stops with the precise missing-file error.

```python
from pathlib import Path
from google.colab import files

candidates = [
    Path("/content/neurovista_inference/Task01_selected/Task01_BrainTumour/labelsTr/BRATS_457.nii.gz"),
    Path("/content/neurovista_inference/Task01_BrainTumour/labelsTr/BRATS_457.nii.gz"),
]
reference = next((path for path in candidates if path.is_file()), None)
if reference is None:
    raise FileNotFoundError(
        "The already-extracted BRATS_457 reference mask is not in this runtime. "
        "This cell will not download the dataset again."
    )
files.download(str(reference))
print(f"Downloading existing reference only: {reference}")
```

Place the downloaded file at `.tmp/prediction-import-BRATS_457/BRATS_457_reference.nii.gz`; `.tmp/` is excluded from Git.

## Independence limitation

This is a **single-case comparison**, not cohort validation. The model metadata says its data source is the BraTS 2018 Challenge dataset, while MSD Task01 states that its BrainTumour task comes from BraTS 2016/2017. Those releases can share subjects, and no authoritative subject-level crosswalk for anonymized `BRATS_457` was established here. Training-set overlap therefore cannot be ruled out. Any resulting Dice values must not be described as independent validation, generalization performance or clinical performance.
