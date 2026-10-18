"""Validate a real MRI/mask pair with the same geometry code used by NeuroVista."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.imaging import label_measurements, label_mesh, load_nifti, orientation_labels, render_slice, validate_mask


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scan", type=Path)
    parser.add_argument("mask", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    scan_img, scan, metadata = load_nifti(args.scan, 768 * 1024**2)
    mask_img, mask, _ = load_nifti(args.mask, 768 * 1024**2)
    labels = validate_mask(scan_img, scan, mask_img, mask)
    measurements = label_measurements(mask, metadata.affine, metadata.units)

    slice_checks = {}
    for plane, axis in (("sagittal", 0), ("coronal", 1), ("axial", 2)):
        index = metadata.shape[axis] // 2
        image = render_slice(scan, mask, plane, index, metadata.intensity[1] - metadata.intensity[0],
                             sum(metadata.intensity) / 2, 0.5, set(labels))
        slice_checks[plane] = {"index": index, "pixel_size": image.size, "orientation_labels": orientation_labels(metadata, plane)}

    meshes = {}
    for label in labels:
        mesh = label_mesh(mask, label, metadata.spacing)
        meshes[str(label)] = {"vertices": len(mesh["vertices"]), "faces": len(mesh["faces"])}

    report = {
        "scan": str(args.scan),
        "mask": str(args.mask),
        "shape": metadata.shape,
        "spacing": metadata.spacing,
        "units": metadata.units,
        "orientation": metadata.orientation,
        "affine_match": True,
        "labels": labels,
        "measurements": measurements,
        "slice_checks": slice_checks,
        "meshes": meshes,
    }
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

