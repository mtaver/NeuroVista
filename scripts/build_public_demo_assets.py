"""Build redistribution-approved static browser assets from one verified local case."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import nibabel as nib
import numpy as np
from skimage.measure import marching_cubes

LABEL_NAMES = {
    1: "Non-enhancing tumour-core region",
    2: "Whole-tumour-only region",
    4: "Enhancing tumour",
}
COLORS = {1: "#24dec7", 2: "#ff6699", 4: "#8777ff"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_gzip(path: Path, payload: bytes) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as stream:
            stream.write(payload)


def mesh_for(mask: np.ndarray, label: int, spacing: np.ndarray, max_faces: int = 30000) -> dict:
    vertices, faces, _normals, _values = marching_cubes(np.pad(mask == label, 1), 0.5, spacing=spacing)
    vertices -= spacing
    if len(faces) > max_faces:
        faces = faces[:: int(np.ceil(len(faces) / max_faces))]
    return {"label": label, "vertices": vertices.round(3).tolist(), "faces": faces.tolist()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scan", type=Path)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    scan_image, mask_image = nib.load(str(args.scan)), nib.load(str(args.prediction))
    scan, mask = np.asarray(scan_image.dataobj), np.asarray(mask_image.dataobj)
    if scan.ndim != 3 or mask.shape != scan.shape:
        raise ValueError("Expected matching 3D scan and prediction")
    if not np.allclose(scan_image.affine, mask_image.affine, rtol=0, atol=1e-6):
        raise ValueError("Prediction affine does not match scan")
    if not np.isfinite(scan).all() or not np.isfinite(mask).all():
        raise ValueError("Public assets require finite voxels")
    labels = sorted(int(value) for value in np.unique(mask) if value)
    if not set(labels).issubset(LABEL_NAMES):
        raise ValueError(f"Unexpected labels: {labels}")

    provenance = json.loads(args.provenance.read_text(encoding="utf-8"))
    comparison = json.loads(args.comparison.read_text(encoding="utf-8"))
    if provenance["input_contract"]["inputs"]["t1c"]["sha256"] != sha256(args.scan):
        raise ValueError("Scan checksum does not match provenance")
    if provenance["output"]["sha256"] != sha256(args.prediction):
        raise ValueError("Prediction checksum does not match provenance")

    low, high = np.percentile(scan, [1, 99])
    display = np.clip((scan.astype(np.float32) - low) / max(float(high - low), 1e-6), 0, 1)
    display = np.rint(display * 255).astype(np.uint8)
    write_gzip(args.output / "scan-display-u8.bin.gz", display.tobytes(order="C"))
    write_gzip(args.output / "prediction-labels-u8.bin.gz", np.rint(mask).astype(np.uint8).tobytes(order="C"))

    spacing = np.asarray(nib.affines.voxel_sizes(scan_image.affine), dtype=float)
    voxel_ml = abs(np.linalg.det(scan_image.affine[:3, :3])) / 1000
    metadata = {
        "case": "BRATS_457",
        "shape": list(scan.shape),
        "spacing_mm": spacing.tolist(),
        "orientation": list(nib.aff2axcodes(scan_image.affine)),
        "display_window_source_percentiles": [float(low), float(high)],
        "scan_sha256": sha256(args.scan),
        "prediction_sha256": sha256(args.prediction),
        "labels": [{"label": label, "name": LABEL_NAMES[label], "color": COLORS[label],
                    "voxels": int(np.count_nonzero(mask == label)),
                    "volume_ml": float(np.count_nonzero(mask == label) * voxel_ml)} for label in labels],
        "dice": {name: comparison["regions"][name]["dice"] for name in ("whole_tumour", "tumour_core", "enhancing_tumour")},
        "independent_validation": False,
        "limitation": comparison["independence_note"],
        "model": {"name": provenance["model"]["name"], "version": provenance["model"]["version"],
                  "licence": provenance["model"]["license"]},
        "run": {"gpu": provenance["hardware"]["gpu"], "inference_seconds": provenance["inference"]["elapsed_seconds"],
                "peak_gpu_memory_gib": provenance["inference"]["peak_gpu_memory_gib"]},
    }
    (args.output / "demo-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    meshes = [mesh_for(np.rint(mask).astype(np.uint8), label, spacing) for label in labels]
    write_gzip(args.output / "prediction-meshes.json.gz", json.dumps(meshes, separators=(",", ":")).encode())

    attribution = """# Public demonstration data attribution

This browser demonstration contains transformed display data derived from Medical Segmentation Decathlon Task01 BrainTumour case BRATS_457.

- Source project: Medical Segmentation Decathlon, https://medicaldecathlon.com/
- Task download listing: https://medicaldecathlon.com/dataaws/
- Citation: Antonelli et al., The Medical Segmentation Decathlon, Nature Communications 13, 4128 (2022), https://doi.org/10.1038/s41467-022-30695-9
- Dataset licence: Creative Commons Attribution-ShareAlike 4.0 International, https://creativecommons.org/licenses/by-sa/4.0/
- Changes: the T1c MRI was intensity-windowed to 8-bit display voxels and gzip-compressed; the precomputed prediction was converted to an 8-bit label buffer; display meshes were derived and decimated. Original NIfTI headers and files are not published.
- AI result: generated previously with Project MONAI `brats_mri_segmentation` v0.5.4 (Apache-2.0 model bundle). It is not an expert label and is not generated by this website.

The transformed dataset-derived assets in this directory are redistributed under CC BY-SA 4.0. Application source code retains its repository licence terms.
"""
    (args.output / "DATA_ATTRIBUTION.md").write_text(attribution, encoding="utf-8")
    print(json.dumps({"shape": list(scan.shape), "labels": labels,
                      "asset_bytes": sum(path.stat().st_size for path in args.output.iterdir())}, indent=2))


if __name__ == "__main__":
    main()
