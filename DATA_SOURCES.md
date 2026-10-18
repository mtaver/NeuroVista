# Data sources

## Recommended official source: Medical Segmentation Decathlon

**Dataset:** Task01 BrainTumour  
**Official project:** https://medicaldecathlon.com/  
**Official AWS download page:** https://medicaldecathlon.com/dataaws/  
**AWS Open Data registry:** https://registry.opendata.aws/msd/  
**Licence:** CC BY-SA 4.0, as documented by the Decathlon publication and dataset materials  
**Format:** NIfTI; four MRI channels per case with voxel-level tumour annotations in the training set  
**Provenance:** The brain task is derived from the BraTS 2016/2017 cases.

The full Task01 archive is several gigabytes and is deliberately not downloaded or committed by this repository.

### Acquisition on Windows

1. Read the dataset description and licence on the official pages above.
2. Install the AWS CLI if needed: `winget install Amazon.AWSCLI`.
3. Create a non-versioned folder outside the source tree, or use the ignored `data` folder.
4. List the public bucket without credentials:

   ```powershell
   aws s3 ls s3://msd-for-monai-eu/ --no-sign-request
   ```

5. Download the Brain Tumour task shown by that listing. The currently documented archive name is `Task01_BrainTumour.tar`; confirm the listing before download:

   ```powershell
   New-Item -ItemType Directory -Force data | Out-Null
   aws s3 cp s3://msd-for-monai-eu/Task01_BrainTumour.tar data\Task01_BrainTumour.tar --no-sign-request
   ```

6. Extract it locally and use a training image together with the corresponding file in `labelsTr`. MSD images are four-channel volumes, whereas the Stage 1 viewer accepts one 3D volume. Extract one modality to its own NIfTI file before upload, while preserving the original affine. The segmentation label map can be uploaded directly if its three-dimensional geometry matches the selected modality.
7. Preserve the required attribution and ShareAlike terms if redistributing derived dataset material.

Do not commit the archive, extracted volumes, or patient-derived data. The repository `.gitignore` excludes the common paths and NIfTI extensions as an additional safeguard.

## Alternative official source: BraTS-PEDs on TCIA

TCIA publishes the BraTS-PEDs collection with NIfTI MR images and expert-refined segmentation masks under CC BY 4.0. Its official page is https://www.cancerimagingarchive.net/collection/brats-peds/. The download is large and uses TCIA's listed access mechanism. NeuroVista does not redistribute it.

## Included synthetic demonstration

The **Synthetic demonstration — not a patient scan** is generated deterministically by the local backend. It contains an ellipsoidal intensity phantom and two nested label regions. It is suitable for testing navigation, overlays, volumes, exports, and 3D surfaces only. It is not a tumour case, is not training data, and must not be used for clinical conclusions.

## Real-data Stage 1 verification

Verified on 2026-10-18 with **Medical Segmentation Decathlon Task04 Hippocampus**, case `hippocampus_001`. The archive came directly from the official MSD AWS host:

`https://msd-for-monai.s3-us-west-2.amazonaws.com/Task04_Hippocampus.tar`

The archive's `dataset.json` identifies the data as MRI, describes left/right hippocampus segmentation, names Vanderbilt University Medical Center as the reference, and declares CC BY-SA 4.0. The official MSD site states that labels were verified by an expert human rater. The downloaded archive and extracted files were kept under ignored `.tmp/real-data/` and were not added to source control.

Validation results for the selected scan/reference pair:

- shape: `35 × 51 × 35`
- voxel spacing: `1.0 × 1.0 × 1.0 mm`
- affine orientation: `R · A · S`
- scan/mask shape and affine: exact match within NeuroVista tolerances
- label 1: 1,324 voxels = **1.324 mL**
- label 2: 1,624 voxels = **1.624 mL**
- axial labels: `L/R`, `A/P`; coronal: `L/R`, `S/I`; sagittal: `P/A`, `S/I`
- overlay PNG generated successfully through the live upload API
- label 1 surface: 1,048 vertices / 2,092 faces
- label 2 surface: 1,476 vertices / 2,948 faces

The repeatable validation command is:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe backend\scripts\validate_case.py `
  <scan.nii.gz> <mask.nii.gz> --output <ignored-report.json>
```

This hippocampus case validates the Stage 1 viewer and geometry pipeline. It is not a brain-tumour case and is not compatible input for the Stage 2 BraTS model.

It specifically validates **MRI viewing, uploaded reference-mask overlays, affine-derived measurements, and 3D rendering**. It does **not** validate tumour segmentation, AI inference, tumour-region accuracy, model performance, diagnostic performance, or suitability for a clinical workflow.

