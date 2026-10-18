from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import nibabel as nib
import numpy as np
from PIL import Image
from skimage.measure import marching_cubes

Plane = Literal["axial", "coronal", "sagittal"]


class ImagingError(ValueError):
    pass


@dataclass(frozen=True)
class ScanMetadata:
    shape: tuple[int, int, int]
    spacing: tuple[float, float, float]
    units: str
    orientation: tuple[str, str, str]
    affine: list[list[float]]
    dtype: str
    intensity: tuple[float, float]

    def as_dict(self) -> dict:
        return {
            "shape": self.shape,
            "spacing": self.spacing,
            "units": self.units,
            "orientation": self.orientation,
            "affine": self.affine,
            "dtype": self.dtype,
            "intensity": self.intensity,
        }


def load_nifti(path: Path, max_decompressed_bytes: int) -> tuple[nib.Nifti1Image, np.ndarray, ScanMetadata]:
    try:
        image = nib.load(str(path))
        shape = tuple(int(v) for v in image.shape)
        if len(shape) < 3 or any(v < 1 for v in shape[:3]):
            raise ImagingError("The NIfTI file must contain a non-empty 3D volume.")
        if len(shape) > 3 and any(v != 1 for v in shape[3:]):
            raise ImagingError("4D or multi-volume NIfTI scans are not supported in Stage 1.")
        estimated = int(np.prod(shape[:3])) * np.dtype(image.get_data_dtype()).itemsize
        if estimated > max_decompressed_bytes:
            raise ImagingError("The decompressed volume exceeds the configured safety limit.")
        affine = np.asarray(image.affine, dtype=np.float64)
        if affine.shape != (4, 4) or not np.isfinite(affine).all() or abs(np.linalg.det(affine[:3, :3])) < 1e-12:
            raise ImagingError("The NIfTI affine is missing, non-finite, or singular.")
        data = np.asarray(image.dataobj).squeeze()
        if data.ndim != 3:
            raise ImagingError("The NIfTI file could not be reduced to one 3D volume.")
        if not np.issubdtype(data.dtype, np.number):
            raise ImagingError("The NIfTI voxel datatype must be numeric.")
        finite = data[np.isfinite(data)]
        if finite.size == 0:
            raise ImagingError("The scan contains no finite voxel values.")
        units = image.header.get_xyzt_units()[0] or "unknown"
        spacing = tuple(float(v) for v in nib.affines.voxel_sizes(affine))
        orientation = tuple(str(v) for v in nib.aff2axcodes(affine))
        low, high = np.percentile(finite.astype(np.float32), [1, 99])
        metadata = ScanMetadata(shape[:3], spacing, units, orientation, affine.tolist(), str(data.dtype), (float(low), float(high)))
        return image, data, metadata
    except ImagingError:
        raise
    except Exception as exc:
        raise ImagingError(f"Unable to read this NIfTI file: {exc}") from exc


def validate_mask(scan_img: nib.Nifti1Image, scan: np.ndarray, mask_img: nib.Nifti1Image, mask: np.ndarray) -> list[int]:
    if mask.shape != scan.shape:
        raise ImagingError(f"Mask dimensions {mask.shape} do not match scan dimensions {scan.shape}.")
    if not np.allclose(mask_img.affine, scan_img.affine, rtol=1e-5, atol=1e-4):
        raise ImagingError("Mask affine geometry does not match the scan. Automatic alignment is intentionally disabled.")
    if not np.isfinite(mask).all():
        raise ImagingError("The mask contains non-finite values.")
    rounded = np.rint(mask)
    if not np.allclose(mask, rounded, atol=1e-6):
        raise ImagingError("Segmentation masks must contain integer label values.")
    labels = sorted(int(v) for v in np.unique(rounded) if v != 0)
    if any(v < 0 for v in labels):
        raise ImagingError("Segmentation label values must be non-negative.")
    if len(labels) > 64:
        raise ImagingError("The mask contains more than 64 foreground labels; check that this is a label map.")
    return labels


def voxel_volume_ml(affine: np.ndarray, units: str) -> float:
    volume = float(abs(np.linalg.det(np.asarray(affine)[:3, :3])))
    factors = {"mm": 1 / 1000, "micron": 1e-12, "meter": 1e6}
    if units not in factors:
        raise ImagingError("Spatial units are unknown; volumes cannot be reported safely.")
    return volume * factors[units]


def label_measurements(mask: np.ndarray, affine: np.ndarray, units: str) -> list[dict]:
    per_voxel = voxel_volume_ml(affine, units)
    return [
        {"label": int(label), "voxels": int(np.count_nonzero(mask == label)), "volume_ml": float(np.count_nonzero(mask == label) * per_voxel)}
        for label in sorted(v for v in np.unique(mask) if v != 0)
    ]


def orientation_labels(meta: ScanMetadata, plane: Plane) -> dict[str, str]:
    pos = {"R": "L", "L": "R", "A": "P", "P": "A", "S": "I", "I": "S"}
    axes = {"sagittal": (1, 2), "coronal": (0, 2), "axial": (0, 1)}[plane]
    horizontal, vertical = (meta.orientation[axes[0]], meta.orientation[axes[1]])
    return {"left": pos[horizontal], "right": horizontal, "top": vertical, "bottom": pos[vertical]}


def slice_array(data: np.ndarray, plane: Plane, index: int) -> np.ndarray:
    axis = {"sagittal": 0, "coronal": 1, "axial": 2}[plane]
    if not 0 <= index < data.shape[axis]:
        raise ImagingError("Slice index is outside the volume.")
    result = np.take(data, index, axis=axis)
    return np.flipud(result.T)


def render_slice(scan: np.ndarray, mask: np.ndarray | None, plane: Plane, index: int, window: float, level: float,
                 opacity: float, visible_labels: set[int]) -> Image.Image:
    source = slice_array(scan, plane, index).astype(np.float32)
    width = max(float(window), 1e-6)
    gray = np.clip((source - (level - width / 2)) / width, 0, 1)
    gray = (gray * 255).astype(np.uint8)
    rgb = np.repeat(gray[..., None], 3, axis=-1).astype(np.float32)
    if mask is not None and visible_labels:
        label_slice = slice_array(mask, plane, index)
        palette = np.asarray([[0, 0, 0], [30, 226, 198], [255, 102, 153], [255, 190, 75], [135, 119, 255], [89, 184, 255]], dtype=np.float32)
        for label in visible_labels:
            selected = label_slice == label
            color = palette[((label - 1) % (len(palette) - 1)) + 1]
            rgb[selected] = rgb[selected] * (1 - opacity) + color * opacity
    return Image.fromarray(rgb.astype(np.uint8))


def label_mesh(mask: np.ndarray, label: int, spacing: tuple[float, float, float], max_faces: int = 150000) -> dict:
    binary = (mask == label).astype(np.uint8)
    if not binary.any():
        raise ImagingError(f"Label {label} is empty.")
    padded = np.pad(binary, 1)
    vertices, faces, _normals, _values = marching_cubes(padded, 0.5, spacing=spacing)
    vertices -= np.asarray(spacing)
    if len(faces) > max_faces:
        stride = int(np.ceil(len(faces) / max_faces))
        faces = faces[::stride]
    return {"label": label, "vertices": vertices.round(4).tolist(), "faces": faces.tolist()}

