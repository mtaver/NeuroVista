# Planned model card: MONAI BraTS MRI segmentation

## Connection status

**AI model not connected.** NeuroVista Stage 1 contains no model weights and performs no AI inference. This document records the authoritative candidate researched for Stage 2; it is not a claim that the model is installed or validated in this application.

## Candidate

- **Bundle:** `brats_mri_segmentation`
- **Authoritative publisher:** Project MONAI Model Zoo
- **Catalog:** https://project-monai.github.io/model-zoo.html
- **Source bundle:** https://github.com/Project-MONAI/model-zoo/tree/dev/models/brats_mri_segmentation
- **Catalog version verified:** 0.5.4
- **Architecture:** SegResNet
- **Model/bundle licence:** Apache License 2.0; the source bundle's own `LICENSE` remains authoritative
- **Purpose:** Brain-tumour subregion segmentation from multimodal MRI
- **Weight availability:** official Hugging Face MONAI repository, `models/model.pt`, 18.8 MB
- **Published weight SHA-256:** `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae`

## Required inputs

The model requires four co-registered MRI sequences for the same subject:

1. T1-weighted
2. contrast-enhanced T1-weighted (T1c/T1ce)
3. T2-weighted
4. FLAIR

The metadata defines the channel order as **T1c, T1, T2, FLAIR**, with 1 mm isotropic, co-aligned four-channel input. A single uploaded sequence is not a valid model input.

The verified bundle configuration performs:

- NIfTI loading with MONAI `LoadImaged`
- nonzero, channel-wise `NormalizeIntensityd`
- SegResNet with 4 input channels and 3 sigmoid output channels
- sliding-window inference with ROI `240 × 240 × 160`, batch size 1, and 0.5 overlap
- sigmoid activation followed by threshold 0.5

Stage 2 must add explicit orientation/spacing handling and invert any spatial preprocessing so predictions are returned to the original reference affine. The published bundle configuration alone must not be assumed to align arbitrary uploads.

## Outputs

The bundle reports three tumour-region channels: tumour core (TC), whole tumour (WT), and enhancing tumour (ET). These are segmentation regions, not tumour-type classification and not a diagnosis.

## Hardware and software

Inference requires PyTorch 2.4-era compatibility, MONAI 1.4-era compatibility, the downloaded bundle, and enough memory for 3D sliding-window processing. The bundle selects CUDA when available and otherwise CPU; it does not publish a minimum RAM/VRAM figure. Exact peak use therefore requires measurement rather than invention.

Hardware observed on the NeuroVista computer on 2026-10-18:

- physical RAM: **7.78 GiB total**, **0.98 GiB free** at inspection time
- GPU: **Intel UHD Graphics 620**, 1 GiB reported adapter memory
- NVIDIA/CUDA: **not available** (`nvidia-smi` absent; no NVIDIA adapter detected)
- PyTorch/MONAI: not installed in the Stage 1 environment

This is not an appropriate configuration for responsibly enabling and validating this 3D BraTS workflow now. CPU execution may technically be possible with sufficient free memory, but no successful real inference has occurred and no compatible four-sequence case has been supplied. NeuroVista therefore remains **AI model not connected**.

A possible future GPU-worker design is assessed in `CLOUD_INFERENCE.md`. It is documentation only: no cloud account, endpoint, storage, GPU, model service, or data transfer has been created.

The repository now includes `notebooks/NeuroVista_MONAI_BraTS_Colab.ipynb` as an executable preparation for a user-initiated Colab run. It pins the documented stack, downloads the versioned official weight, verifies its published SHA-256, validates the four inputs, performs the documented normalization and sliding-window inference, and exports an original-geometry prediction package. **It has not been run on a Colab GPU in this project, so GPU execution remains unverified and the application remains AI model not connected.**

## Known limitations

- Trained for the BraTS-style four-sequence protocol and labels; performance may not transfer to other acquisition protocols, pathologies, populations, or post-treatment appearances.
- Requires correctly co-registered sequences and validated geometry.
- Does not classify tumour type, establish a diagnosis, or replace expert review.
- Published weights and training-data terms are distinct; both must be respected.
- Application-level accuracy claims require representative evaluation and cannot be inferred from a few samples.

## Stage 2 acceptance gates

- pin and verify the actual downloaded bundle version and checksum
- capture its included licence, metadata, preprocessing, label mapping, and validation references
- validate four input sequences and their spatial compatibility
- run real weights only; never fabricate output
- preserve and test original-space geometry
- report actual device, progress, and actionable failures
- evaluate per-region Dice only when an expert reference exists; define both-empty regions as “not applicable,” not a perfect result

