# Running the NeuroVista MONAI notebook in Google Colab

## What has and has not been verified

The notebook has been checked locally against the versioned MONAI `brats_mri_segmentation` **v0.5.4** bundle. Its architecture, channel order, normalization, inference window, activation, threshold and label conversion match the release configuration. Its Python cells parse locally and the official model weight checksum has been verified.

This is preparation verification only. A real Colab GPU inference has **not** completed for this project. Do not describe the model as connected or the run as successful unless the inference cell finishes, the export cell finishes, and the downloaded NIfTI reopens with the expected shape and affine.

## Recommended public research case

Use training case `BRATS_457.nii.gz` from **Medical Segmentation Decathlon Task01 — BrainTumour**. This is tumour MRI data derived from BraTS 2016/2017, not the hippocampus case. The official dataset metadata states:

- four co-registered channels in one 4D NIfTI: `0=FLAIR`, `1=T1w`, `2=T1gd`, `3=T2w`;
- 484 training cases with masks and 266 test cases;
- licence: **CC BY-SA 4.0**;
- `BRATS_457.nii.gz` is a listed training image with a corresponding expert mask.

No account or registration is required for the MONAI-hosted MSD archive. It is approximately **7.1 GiB**, so check disk space and network allowance first. The archive MD5 published by MONAI 1.4.0 is `240a19d752f0d9e9101544901065d872`.

1. Download `Task01_BrainTumour.tar` from the official MONAI MSD mirror:
   `https://msd-for-monai.s3-us-west-2.amazonaws.com/Task01_BrainTumour.tar`
2. Verify its MD5 in PowerShell:

   ```powershell
   Get-FileHash .\Task01_BrainTumour.tar -Algorithm MD5
   ```

3. Extract only the chosen image, its expert mask, and the dataset metadata:

   ```powershell
   tar -xf .\Task01_BrainTumour.tar Task01_BrainTumour/imagesTr/BRATS_457.nii.gz Task01_BrainTumour/labelsTr/BRATS_457.nii.gz Task01_BrainTumour/dataset.json
   ```

4. Keep `dataset.json` with the case so the source, channel definitions and licence remain documented.
5. From the NeuroVista repository, split the 4D image into four aligned volumes:

   ```powershell
   .\.venv\Scripts\python.exe .\scripts\prepare_msd_brats_case.py .\Task01_BrainTumour\imagesTr\BRATS_457.nii.gz .\BRATS_457_split
   ```

   The outputs are suffixed `_flair`, `_t1`, `_t1c`, and `_t2`. The helper only separates channels and preserves the source affine; it does not register or resample them. Keep the expert mask local unless you later want a separate, clearly labelled reference comparison. The model does not need it for inference.

## Colab steps

### 1. Open the notebook

Go to `https://colab.research.google.com/`, choose **File → Upload notebook**, and select `notebooks/NeuroVista_MONAI_BraTS_Colab.ipynb` from this repository. Uploading the notebook itself does not upload an MRI.

### 2. Select and check a GPU

Choose **Runtime → Change runtime type → Hardware accelerator → GPU**, then save. Colab free-tier GPU availability is not guaranteed and the GPU model can vary.

Python 3.12.13 and a Tesla T4 have now been observed in the intended Colab session. That confirms the selected runtime identity only; it does not verify inference, memory sufficiency, output validity or model performance.

Run the installation cell, then the hardware-check cell. Continue only if it prints `"cuda_available": true`. Record the displayed GPU name, VRAM and available RAM. If it raises “A CUDA GPU runtime is required,” use **Runtime → Disconnect and delete runtime** and try later; do not purchase or provision anything for this guide.

### 3. Install the pinned dependencies

Run the first code cell. It first requires Python 3.12 and then installs the adapted pinned stack. The original bundle metadata used NumPy 1.24.4; the Colab adaptation uses NumPy 1.26.4 because it supplies Python 3.12 wheels. PyTorch 2.4.0, MONAI 1.4.0, the model architecture, weights and inference behavior remain unchanged. Matching torchvision 0.19.0 and torchaudio 2.4.0 prevent mismatches with Colab's preinstalled PyTorch family.

After installation, choose **Runtime → Restart session**, then run the hardware/version-check cell. It rejects any package-version mismatch before weights or data are used. This is a pinned Python 3.12 adaptation of the v0.5.4 inference environment, not the bundle's original NumPy-exact environment.

### 4. Upload only the de-identified case

Run the upload cell and select only these four files from `BRATS_457_split`:

- `BRATS_457_t1c.nii.gz`
- `BRATS_457_t1.nii.gz`
- `BRATS_457_t2.nii.gz`
- `BRATS_457_flair.nii.gz`

This transfers those files to Google's Colab environment. Do not upload names, IDs, dates of birth, clinical documents, DICOM headers, or identifiable data. The MSD case is distributed as research data under its stated licence, but you must still follow your institution's policy and Google's current terms.

Edit the `INPUTS` cell so each key points to the matching `/content/...` filename. Do not use the MSD source channel order directly: the model order is fixed as **T1c, T1, T2, FLAIR**. Run the validation cell. It must report four channels, matching shapes and affines, millimetre units and approximately 1 mm isotropic spacing.

### 5. Run real inference

Run the weight-download cell. It must print version `0.5.4` and SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`.

Then run the inference cell. This is the first actual GPU execution. It uses the release's SegResNet, a `240×240×160` sliding window, batch size 1, overlap 0.5, sigmoid activation and threshold 0.5. If it reports CUDA out of memory, the precise blocker is insufficient GPU VRAM for this release-exact inference window. Do not claim success and do not alter the window while describing the result as exact v0.5.4 execution.

### 6. Export and download results

Run the export cell only after inference finishes. It applies the release's exact precedence:

- enhancing tumour channel → label `4`;
- otherwise tumour core channel → label `1`;
- otherwise whole tumour channel → label `2`;
- otherwise background → label `0`.

The browser should download `neurovista_prediction_package.zip`, containing:

- `neurovista_ai_prediction.nii.gz`;
- `neurovista_ai_prediction_provenance.json`;
- `README_IMPORT.txt`.

The export cell reopens the mask and verifies its shape and affine against the uploaded T1c reference. Only successful completion of both inference and export constitutes a valid technical run; it is not clinical validation.

### 7. Import into local NeuroVista

1. Start NeuroVista locally using the repository's README instructions.
2. Upload `BRATS_457_t1c.nii.gz` as the scan.
3. In the mask provenance selector, choose **AI prediction import**.
4. Upload `neurovista_ai_prediction.nii.gz`.
5. Confirm NeuroVista labels it **AI PREDICTION · IMPORTED**, accepts the geometry, and displays labels `1`, `2`, and/or `4` as present.
6. Keep the JSON provenance file beside the NIfTI. Do not relabel the prediction as an expert reference.

The optional `BRATS_457` expert mask uses the MSD source label convention and is not required for this import procedure. A quantitative model evaluation needs an explicitly reviewed label-conversion and metric protocol; visual overlap alone is not a performance claim.

## Cleanup

After the ZIP is safely downloaded, set `CLEAN_UP_NOW = True` and run the notebook's cleanup cell. Then choose **Runtime → Disconnect and delete runtime**. Deleting runtime files is not a guarantee about infrastructure-level retention; consult Google's current Colab privacy and retention terms.

## Precise blockers

- **No GPU assigned / `cuda_available` false:** free Colab GPU capacity is unavailable. Try later.
- **Python check or pinned package installation fails:** the current Colab runtime does not match the verified Python 3.12 adapted stack.
- **Archive download unavailable or insufficient disk/network:** the official MSD archive is about 7.1 GiB; no smaller official per-case endpoint was verified here.
- **Validation rejects spacing, shape, affine or units:** the selected files are not a compatible aligned case or were mapped incorrectly.
- **CUDA out of memory:** the assigned GPU lacks memory for the release-exact inference configuration.
- **Export geometry check fails:** no valid result package exists; do not import or report success.
