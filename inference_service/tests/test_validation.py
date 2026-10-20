from pathlib import Path
import nibabel as nib
import numpy as np
import pytest

from app.inference import CHANNEL_ORDER, load_and_validate


def write_case(root: Path, affine=None):
    affine = np.eye(4) if affine is None else affine
    paths = {}
    for name in CHANNEL_ORDER:
        path = root / f"{name}.nii.gz"
        image = nib.Nifti1Image(np.ones((8, 9, 10), dtype=np.float32), affine)
        image.header.set_xyzt_units("mm"); nib.save(image, path); paths[name] = path
    return paths


def test_valid_case_preserves_t1c_geometry(tmp_path):
    paths = write_case(tmp_path)
    reference, arrays, manifest = load_and_validate(paths, 10 * 1024**2)
    assert reference.shape == (8, 9, 10)
    assert list(arrays) == list(CHANNEL_ORDER)
    assert manifest["t1c"]["spacing_mm"] == [1.0, 1.0, 1.0]


def test_rejects_nonfinite_voxel(tmp_path):
    paths = write_case(tmp_path)
    data = np.ones((8, 9, 10), dtype=np.float32); data[0, 0, 0] = np.nan
    image = nib.Nifti1Image(data, np.eye(4)); image.header.set_xyzt_units("mm"); nib.save(image, paths["t2"])
    with pytest.raises(ValueError, match="finite"):
        load_and_validate(paths, 10 * 1024**2)


def test_rejects_geometry_mismatch(tmp_path):
    paths = write_case(tmp_path)
    shifted = np.eye(4); shifted[0, 3] = 2
    image = nib.Nifti1Image(np.ones((8, 9, 10), dtype=np.float32), shifted); image.header.set_xyzt_units("mm"); nib.save(image, paths["flair"])
    with pytest.raises(ValueError, match="affine"):
        load_and_validate(paths, 10 * 1024**2)
