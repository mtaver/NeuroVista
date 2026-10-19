"""Compare a NeuroVista BraTS prediction with an MSD Task01 expert mask."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np


REFERENCE_LABELS = {
    0: "background",
    1: "edema",
    2: "non-enhancing tumour",
    3: "enhancing tumour",
}
PREDICTION_LABELS = {
    0: "background",
    1: "tumour-core remainder",
    2: "whole-tumour-only remainder",
    4: "enhancing tumour",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def region_masks(reference: np.ndarray, prediction: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return {
        "whole_tumour": (np.isin(reference, (1, 2, 3)), np.isin(prediction, (1, 2, 4))),
        "tumour_core": (np.isin(reference, (2, 3)), np.isin(prediction, (1, 4))),
        "enhancing_tumour": (reference == 3, prediction == 4),
    }


def dice_result(reference: np.ndarray, prediction: np.ndarray) -> dict:
    reference_voxels = int(np.count_nonzero(reference))
    prediction_voxels = int(np.count_nonzero(prediction))
    intersection_voxels = int(np.count_nonzero(reference & prediction))
    if reference_voxels == 0 and prediction_voxels == 0:
        return {
            "dice": None,
            "status": "not_applicable_both_empty",
            "reference_voxels": 0,
            "prediction_voxels": 0,
            "intersection_voxels": 0,
        }
    dice = 2.0 * intersection_voxels / (reference_voxels + prediction_voxels)
    return {
        "dice": float(dice),
        "status": "one_empty" if reference_voxels == 0 or prediction_voxels == 0 else "calculated",
        "reference_voxels": reference_voxels,
        "prediction_voxels": prediction_voxels,
        "intersection_voxels": intersection_voxels,
    }


def compare(reference_path: Path, prediction_path: Path) -> dict:
    reference_image = nib.load(str(reference_path))
    prediction_image = nib.load(str(prediction_path))
    reference = np.asarray(reference_image.dataobj)
    prediction = np.asarray(prediction_image.dataobj)

    if reference.ndim != 3 or prediction.ndim != 3:
        raise ValueError("Reference and prediction must each be one 3D NIfTI volume")
    if reference.shape != prediction.shape:
        raise ValueError(f"Shape mismatch: reference {reference.shape}, prediction {prediction.shape}")
    if not np.allclose(reference_image.affine, prediction_image.affine, rtol=0, atol=1e-6):
        raise ValueError("Affine mismatch: comparison requires identical scan geometry")
    if not np.isfinite(reference).all() or not np.isfinite(prediction).all():
        raise ValueError("Reference and prediction must contain only finite values")
    if not np.allclose(reference, np.rint(reference)) or not np.allclose(prediction, np.rint(prediction)):
        raise ValueError("Reference and prediction labels must be integers")

    reference = np.rint(reference).astype(np.int16)
    prediction = np.rint(prediction).astype(np.int16)
    actual_reference_labels = sorted(int(value) for value in np.unique(reference))
    actual_prediction_labels = sorted(int(value) for value in np.unique(prediction))
    unsupported_reference = sorted(set(actual_reference_labels) - set(REFERENCE_LABELS))
    unsupported_prediction = sorted(set(actual_prediction_labels) - set(PREDICTION_LABELS))
    if unsupported_reference:
        raise ValueError(f"Unsupported MSD reference labels: {unsupported_reference}")
    if unsupported_prediction:
        raise ValueError(f"Unsupported prediction labels: {unsupported_prediction}")

    regions = {name: dice_result(ref, pred) for name, (ref, pred) in region_masks(reference, prediction).items()}
    return {
        "comparison_scope": "single_case",
        "independent_validation": False,
        "independence_note": "MSD Task01 derives from BraTS 2016/2017 while the model reports BraTS 2018 training; subject overlap has not been ruled out.",
        "geometry": {
            "shape": list(reference.shape),
            "affine": reference_image.affine.tolist(),
            "spacing": [float(value) for value in reference_image.header.get_zooms()[:3]],
            "axis_codes": list(nib.aff2axcodes(reference_image.affine)),
        },
        "reference": {
            "path": str(reference_path),
            "sha256": sha256_file(reference_path),
            "label_definitions": {str(key): value for key, value in REFERENCE_LABELS.items()},
            "actual_labels": actual_reference_labels,
        },
        "prediction": {
            "path": str(prediction_path),
            "sha256": sha256_file(prediction_path),
            "label_definitions": {str(key): value for key, value in PREDICTION_LABELS.items()},
            "actual_labels": actual_prediction_labels,
        },
        "region_mapping": {
            "whole_tumour": {"reference": [1, 2, 3], "prediction": [1, 2, 4]},
            "tumour_core": {"reference": [2, 3], "prediction": [1, 4]},
            "enhancing_tumour": {"reference": [3], "prediction": [4]},
        },
        "empty_region_policy": "Both empty is not applicable (dice null); exactly one empty is dice 0.",
        "regions": regions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.reference, args.prediction)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
