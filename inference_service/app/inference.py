from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import nibabel as nib
import numpy as np

CHANNEL_ORDER = ("t1c", "t1", "t2", "flair")
MODEL_VERSION = "0.5.4"
MODEL_SOURCE = "https://huggingface.co/MONAI/brats_mri_segmentation/tree/0.5.4"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate(inputs: dict[str, Path], max_decompressed_bytes: int):
    images, arrays, manifest = {}, {}, {}
    for modality in CHANNEL_ORDER:
        path = inputs[modality]
        image = nib.load(str(path))
        shape = tuple(int(value) for value in image.shape)
        if len(shape) != 3 or any(value < 1 for value in shape):
            raise ValueError(f"{modality}: expected one non-empty 3D NIfTI volume")
        estimate = int(np.prod(shape)) * np.dtype(image.get_data_dtype()).itemsize
        if estimate > max_decompressed_bytes:
            raise ValueError(f"{modality}: decompressed volume exceeds the configured limit")
        values = np.asarray(image.dataobj)
        affine = np.asarray(image.affine, dtype=np.float64)
        if not np.issubdtype(values.dtype, np.number) or not np.isfinite(values).all():
            raise ValueError(f"{modality}: voxels must be finite numeric values")
        if affine.shape != (4, 4) or not np.isfinite(affine).all() or abs(np.linalg.det(affine[:3, :3])) < 1e-12:
            raise ValueError(f"{modality}: affine is invalid")
        units = image.header.get_xyzt_units()[0]
        spacing = np.asarray(nib.affines.voxel_sizes(affine))
        if units != "mm":
            raise ValueError(f"{modality}: spatial units must be millimetres")
        if not np.allclose(spacing, (1, 1, 1), rtol=0, atol=1e-3):
            raise ValueError(f"{modality}: model requires 1 mm spacing; received {spacing.tolist()}")
        images[modality], arrays[modality] = image, values.astype(np.float32, copy=False)
        manifest[modality] = {
            "sha256": sha256_file(path), "shape": list(shape), "affine": affine.tolist(),
            "spacing_mm": spacing.tolist(), "axis_codes": list(nib.aff2axcodes(affine)),
        }
    reference = images["t1c"]
    for modality in CHANNEL_ORDER[1:]:
        if images[modality].shape != reference.shape:
            raise ValueError(f"{modality}: dimensions do not match T1c")
        if not np.allclose(images[modality].affine, reference.affine, rtol=1e-5, atol=1e-4):
            raise ValueError(f"{modality}: affine does not match T1c; automatic registration is disabled")
    return reference, arrays, manifest


def run_inference(inputs: dict[str, Path], output_dir: Path, model_path: Path, expected_sha256: str,
                  max_decompressed_bytes: int) -> dict:
    import monai
    import torch
    from monai.inferers import sliding_window_inference
    from monai.networks.nets import SegResNet
    from monai.transforms import NormalizeIntensity

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is unavailable")
    actual_weight_sha = sha256_file(model_path)
    if actual_weight_sha.lower() != expected_sha256.lower():
        raise RuntimeError("official model weight checksum mismatch")
    reference, arrays, input_manifest = load_and_validate(inputs, max_decompressed_bytes)
    stacked = np.stack([arrays[name] for name in CHANNEL_ORDER], axis=0)
    normalized = NormalizeIntensity(nonzero=True, channel_wise=True)(stacked)
    model_input = torch.as_tensor(np.asarray(normalized), dtype=torch.float32).unsqueeze(0)
    device = torch.device("cuda:0")
    model = SegResNet(spatial_dims=3, init_filters=16, in_channels=4, out_channels=3,
                      dropout_prob=0.2, blocks_down=(1, 2, 2, 4), blocks_up=(1, 1, 1)).to(device)
    checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint.get("model", checkpoint) if isinstance(checkpoint, dict) else checkpoint, strict=True)
    model.eval()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with torch.inference_mode():
        logits = sliding_window_inference(
            model_input.to(device), roi_size=(240, 240, 160), sw_batch_size=1,
            predictor=lambda window: model(window), overlap=0.5,
            device=torch.device("cpu"), sw_device=device,
        )
    elapsed = time.perf_counter() - started
    channels = (torch.sigmoid(logits)[0] >= 0.5).cpu().numpy()
    if channels.shape != (3, *reference.shape):
        raise RuntimeError("model returned an unexpected output shape")
    tc, wt, et = channels
    labels = np.zeros(reference.shape, dtype=np.uint8)
    labels[wt], labels[tc], labels[et] = 2, 1, 4
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction = output_dir / "neurovista_ai_prediction.nii.gz"
    header = reference.header.copy(); header.set_data_dtype(np.uint8)
    nib.save(nib.Nifti1Image(labels, reference.affine.copy(), header), prediction)
    reloaded = nib.load(str(prediction))
    if reloaded.shape != reference.shape or not np.allclose(reloaded.affine, reference.affine, rtol=0, atol=1e-6):
        raise RuntimeError("prediction could not be restored to T1c reference geometry")
    provenance = {
        "application": "NeuroVista portable GPU inference service",
        "research_only": True,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": {"name": "brats_mri_segmentation", "version": MODEL_VERSION, "architecture": "SegResNet",
                  "source": MODEL_SOURCE, "weight_sha256": actual_weight_sha, "licence": "Apache-2.0"},
        "software": {"python": platform.python_version(), "torch": torch.__version__, "monai": monai.__version__,
                     "numpy": np.__version__, "nibabel": nib.__version__},
        "hardware": {"gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda,
                     "peak_gpu_memory_gib": torch.cuda.max_memory_allocated() / 1024**3},
        "input_contract": {"channel_order": list(CHANNEL_ORDER), "reference": "t1c", "inputs": input_manifest},
        "preprocessing": {"spatial_transform": "none; aligned 1 mm geometry required",
                          "intensity": "NormalizeIntensity(nonzero=True, channel_wise=True)"},
        "inference": {"roi_size": [240, 240, 160], "overlap": 0.5, "activation": "sigmoid",
                      "threshold": 0.5, "elapsed_seconds": elapsed},
        "output": {"filename": prediction.name, "sha256": sha256_file(prediction), "shape": list(reloaded.shape),
                   "affine": reloaded.affine.tolist(), "labels": {"0": "background", "1": "Non-enhancing tumour-core region",
                   "2": "Whole-tumour-only region", "4": "Enhancing tumour"}},
        "limitations": ["Research and education only", "Not diagnostic accuracy", "Expert review required"],
    }
    provenance_path = output_dir / "neurovista_ai_prediction_provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance

