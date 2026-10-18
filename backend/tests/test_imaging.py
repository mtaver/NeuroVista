import nibabel as nib
import numpy as np
import pytest

from app.imaging import ImagingError, ScanMetadata, orientation_labels, validate_mask, voxel_volume_ml


def image(shape=(8, 9, 10), affine=None):
    affine = np.diag([1.0, 2.0, 3.0, 1.0]) if affine is None else affine
    result = nib.Nifti1Image(np.zeros(shape, dtype=np.float32), affine)
    result.header.set_xyzt_units("mm")
    return result


def test_volume_calculation_from_affine_in_ml():
    assert voxel_volume_ml(np.diag([1.0, 2.0, 3.0, 1.0]), "mm") == pytest.approx(0.006)


def test_mask_requires_matching_dimensions():
    scan, mask = image(), image((8, 9, 11))
    with pytest.raises(ImagingError, match="dimensions"):
        validate_mask(scan, np.zeros((8, 9, 10)), mask, np.zeros((8, 9, 11)))


def test_mask_requires_matching_affine():
    scan, mask = image(), image(affine=np.diag([1.0, 2.0, 4.0, 1.0]))
    with pytest.raises(ImagingError, match="affine"):
        validate_mask(scan, np.zeros((8, 9, 10)), mask, np.zeros((8, 9, 10)))


def test_mask_rejects_fractional_labels():
    scan, mask = image(), image()
    values = np.zeros((8, 9, 10)); values[0, 0, 0] = 1.5
    with pytest.raises(ImagingError, match="integer"):
        validate_mask(scan, np.zeros_like(values), mask, values)


def test_orientation_labels_come_from_affine_axes():
    meta = ScanMetadata((8, 9, 10), (1, 1, 1), "mm", ("R", "A", "S"), np.eye(4).tolist(), "float32", (0, 1))
    assert orientation_labels(meta, "axial") == {"left": "L", "right": "R", "top": "A", "bottom": "P"}

