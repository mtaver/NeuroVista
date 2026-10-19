"""Split one official MSD Task01 4D BraTS image into NeuroVista model inputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import nibabel as nib
import numpy as np


MSD_CHANNELS = ("flair", "t1", "t1c", "t2")


def split_case(source: Path, output_dir: Path) -> list[Path]:
    image = nib.load(str(source))
    data = np.asanyarray(image.dataobj)
    if data.ndim != 4 or data.shape[-1] != 4:
        raise ValueError(f"Expected an MSD 4D image with four channels last; received {data.shape}")
    if not np.isfinite(data).all():
        raise ValueError("The source contains non-finite values")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for index, modality in enumerate(MSD_CHANNELS):
        destination = output_dir / f"{source.name.removesuffix('.nii.gz').removesuffix('.nii')}_{modality}.nii.gz"
        header = image.header.copy()
        header.set_data_shape(data.shape[:3])
        nib.save(nib.Nifti1Image(data[..., index], image.affine.copy(), header=header), destination)
        outputs.append(destination)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split MSD Task01 channel order FLAIR,T1,T1gd,T2 into four aligned NIfTI files."
    )
    parser.add_argument("source", type=Path, help="Task01_BrainTumour/imagesTr/BRATS_*.nii.gz")
    parser.add_argument("output_dir", type=Path, help="Directory for the four de-identified outputs")
    args = parser.parse_args()
    for result in split_case(args.source, args.output_dir):
        print(result)


if __name__ == "__main__":
    main()
