# Cloud-GPU inference assessment

## Status and boundary

NeuroVista remains **Local inference not connected**. One user-initiated Colab run produced files that were downloaded and imported locally as **Cloud-generated AI prediction imported**. There is no live Colab connection, configured endpoint, background synchronization or paid resource provisioned by NeuroVista.

The opt-in notebook at `notebooks/NeuroVista_MONAI_BraTS_Colab.ipynb` completed one real `BRATS_457` run. The resulting hashes, geometry, labels, overlays, measurements and 3D meshes were verified locally. Expert comparison produced Dice 0.896640 whole tumour, 0.834695 tumour core and 0.831881 enhancing tumour. This establishes a single-case technical demonstration only; it does not establish diagnostic accuracy, independence, cohort performance or clinical suitability. Possible training-subject overlap remains unresolved.

The proposed boundary keeps all viewing, mask inspection, measurements, exports, and session management local. A GPU worker would be used only for an explicitly initiated inference job after the user reviews what will be sent and where.

## Required input contract

One inference case must contain four MRI volumes from the same subject and examination, in this exact model channel order:

1. contrast-enhanced T1 (`T1c`/`T1ce`)
2. native T1
3. T2
4. FLAIR

Before any transfer, the local service must verify:

- each input is one finite 3D NIfTI volume
- dimensions, affine, orientation, voxel spacing, and spatial units are valid
- the four volumes are already co-registered to the same physical space
- the matrices and affines match within documented tolerances; no silent alignment
- the user has deliberately assigned each sequence to its channel
- decompressed sizes and total job size are within limits
- identifiers have been removed when required by the applicable governance policy

The tested hippocampus sample is a single MRI volume and is not valid model input.

## Proposed flow

```text
Local NeuroVista
  validate four inputs and record original reference geometry
            |
            | explicit user-authorized, encrypted job submission
            v
Ephemeral private GPU worker
  verify manifest and checksums
  load pinned MONAI bundle + verified weights
  normalize nonzero voxels channel-wise
  run 240×240×160 sliding-window inference, batch 1, overlap 0.5
  threshold TC / WT / ET output channels
  invert spatial transforms to the original reference grid
            |
            | encrypted result + signed processing manifest
            v
Local NeuroVista
  revalidate shape, affine, labels and checksums
  store temporarily, display as “AI prediction,” and delete remotely
```

The first proof of concept should use an ephemeral job rather than a permanently running endpoint. The worker should have no public unauthenticated route, no durable scan bucket by default, outbound access restricted after model retrieval, encrypted temporary storage, short retention, structured audit logs without image data, and an automatic delete-on-success/failure policy. Clinical or identifiable data would require a separate governance, jurisdiction, contractual, and security review.

## Geometry preservation

The local manifest should retain, for every sequence:

- original shape, affine, axis codes, spacing, spatial units and header identifiers needed for reconstruction
- SHA-256 of the uploaded bytes
- the selected reference sequence, normally T1c for this bundle
- every deterministic preprocessing transform and its parameters

Inference preprocessing should use MONAI metadata-aware transforms. If reorientation, resampling, padding, or cropping is added, it must be invertible and recorded. Postprocessing must invert those transforms in reverse order, use nearest-neighbour interpolation for discrete masks, and write the result with the reference volume's original shape and affine. The local service must reject a returned result unless its declared reference checksum, shape, affine and label schema match the submitted job.

The returned label map should distinguish the model's nested channels—tumour core (TC), whole tumour (WT), and enhancing tumour (ET)—from the original BraTS integer label convention. NeuroVista must not relabel these as tumour types or diagnostic classes.

## Estimated pilot resources

These are planning estimates, not measured requirements or a purchasing recommendation:

| Resource | Pilot target | Basis / caveat |
|---|---:|---|
| NVIDIA GPU | 1 GPU with **24 GiB VRAM** preferred | The published ROI is 240×240×160. An official MONAI discussion reports an out-of-memory result at 12 GB and suggests reducing ROI; 24 GB gives safer headroom but must still be benchmarked. |
| Minimum experiment | **16 GiB VRAM** with reduced ROI | May trade speed for memory and can still fail; exact compatibility must be measured. Do not silently change ROI in production. |
| System RAM | **32 GiB preferred**, 16 GiB minimum pilot | Four float32 volumes, preprocessing copies, worker processes, output probabilities and serialization require headroom. This is an engineering estimate, not a bundle guarantee. |
| CPU | 4–8 vCPU | NIfTI decompression, checksums, resampling and serialization; inference remains GPU-bound. |
| Temporary disk | 10–20 GiB encrypted | Bundle/environment plus input, intermediate and output files. Actual case sizes and container layers vary. |
| Software | CUDA-compatible PyTorch 2.4-era stack, MONAI 1.4-era stack | Match the v0.5.4 bundle metadata first; test newer versions separately. |

The bundle does not publish a formal minimum VRAM or RAM specification. A synthetic tensor test is insufficient: sizing must be confirmed with a legally usable, properly co-registered four-sequence case and the exact container image. No provider or instance type should be selected until that benchmark exists.

## Result package

The worker should return a small, versioned archive containing:

- prediction NIfTI in the original reference geometry
- processing manifest with bundle version, weight SHA-256, container digest, device model, software versions, input checksums and transform history
- per-stage timestamps measured by the worker
- explicit label/channel mapping
- failure details without fabricated partial predictions

The local application should independently reopen and validate the returned NIfTI before display. Only then may it change the provenance label to **AI prediction**. A successful transport or HTTP response is not evidence of valid inference.

## Go/no-go gates

Cloud inference must remain disabled until all of the following pass:

- privacy and data-location decision, including explicit upload consent UX
- pinned container and dependency build
- weight checksum and licence capture
- four-sequence validation and channel-order tests
- original-geometry round-trip tests using nontrivial affines and anisotropic spacing
- measured GPU/RAM/runtime results on a compatible public case
- failure, cancellation, timeout and remote-deletion tests
- local verification of the returned prediction

Until a local model is deliberately installed and validated, the accurate application state is **Local inference not connected**. Imported result files must be labelled **Cloud-generated AI prediction imported**, never as a live connection.

## Technical references

- MONAI bundle metadata and channel contract: https://github.com/Project-MONAI/model-zoo/blob/dev/models/brats_mri_segmentation/configs/metadata.json
- MONAI preprocessing and sliding-window configuration: https://github.com/Project-MONAI/model-zoo/blob/dev/models/brats_mri_segmentation/configs/train.json
- Official v0.5.4 bundle location: https://huggingface.co/MONAI/brats_mri_segmentation/tree/0.5.4
- MONAI discussion documenting a 12 GB VRAM out-of-memory report and reduced-ROI suggestion: https://github.com/Project-MONAI/MONAI/discussions/5955
