# NeuroVista public browser demonstration

## Scope

The public site is a static, browser-only NIfTI workspace and presentation of the preserved BRATS_457 workflow. It has no Python backend, network upload endpoint, inference endpoint, credential, paid resource or server-side storage. User-selected files are read only into volatile browser memory and are not transmitted or retained.

Public URL: https://mtaver.github.io/NeuroVista/

Working online features:

- local `.nii` and `.nii.gz` scan selection with file-size, three-dimensionality, datatype, finite-value, spatial-unit and affine validation
- optional matching-mask selection with required source labelling, dimension and affine compatibility checks
- linked axial, coronal and sagittal T1c slice navigation
- voxel-derived mask volumes and affine-preserving 3D surfaces generated locally in the browser
- precomputed AI segmentation overlay, per-region visibility and opacity
- recorded affine-derived region volumes
- interactive rotate/zoom 3D surfaces with independent opacity
- recorded whole-tumour, tumour-core and enhancing-tumour Dice values
- explicit single-case, non-independent-validation and possible training-overlap limitations
- dataset, licence, transformation and model attribution

Selecting a local file does not upload it: the static page has no receiving endpoint. **Clear session** discards the current in-memory scan and mask. Hosted inference and automatic AI analysis remain disabled; uploaded masks retain the source category selected by the user and are never automatically described as AI predictions.

## Published assets

Only the files in `public_demo_src/public/assets` are published. They are deterministic transformed derivatives built from the locally preserved, checksum-verified files by `scripts/build_public_demo_assets.py`:

- gzip-compressed 8-bit display voxels from the T1c scan
- gzip-compressed 8-bit precomputed prediction labels
- gzip-compressed decimated display meshes
- non-identifying geometry, volume, model and comparison metadata
- attribution and redistribution terms

Original NIfTI files, the expert reference mask, Colab packages, provenance paths and `.tmp` are not published. The expert mask is used only as the source of the already recorded comparison values.

The source dataset is Medical Segmentation Decathlon Task01 BrainTumour, case BRATS_457. MSD declares its datasets CC BY-SA 4.0. The transformed dataset-derived assets are redistributed with attribution and ShareAlike terms in `public_demo_src/public/assets/DATA_ATTRIBUTION.md`.

## Build

```powershell
Set-Location frontend
npm ci
npm run build:public
```

The output is `public_demo_dist`, which is ignored because GitHub Actions rebuilds it from tracked source and public assets.

## Hosting

`.github/workflows/pages.yml` deploys the static output to GitHub Pages from `main`. The repository is public and GitHub lists Pages and public-repository Actions under its $0 Free plan. Pages supplies HTTPS on `github.io`; no payment method, upgrade or billable cloud service is required by this project.

