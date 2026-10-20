# NeuroVista public browser demonstration

## Scope

The public site is a static, browser-only presentation of the preserved BRATS_457 workflow. It has no Python backend, upload endpoint, inference endpoint, credential, paid resource or server-side storage.

Public URL: https://mtaver.github.io/NeuroVista/

Working online features:

- linked axial, coronal and sagittal T1c slice navigation
- precomputed AI segmentation overlay, per-region visibility and opacity
- recorded affine-derived region volumes
- interactive rotate/zoom 3D surfaces with independent opacity
- recorded whole-tumour, tumour-core and enhancing-tumour Dice values
- explicit single-case, non-independent-validation and possible training-overlap limitations
- dataset, licence, transformation and model attribution

Uploads are deliberately absent. Hosted inference remains disabled. Users who need local NIfTI upload and geometry validation must run the local application.

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

