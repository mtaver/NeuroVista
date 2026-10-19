import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.compare_brats_regions import dice_result, region_masks


def test_region_mapping_matches_msd_and_prediction_definitions():
    reference = np.array([0, 1, 2, 3])
    prediction = np.array([0, 2, 1, 4])
    regions = region_masks(reference, prediction)
    assert regions["whole_tumour"][0].tolist() == [False, True, True, True]
    assert regions["whole_tumour"][1].tolist() == [False, True, True, True]
    assert regions["tumour_core"][0].tolist() == [False, False, True, True]
    assert regions["tumour_core"][1].tolist() == [False, False, True, True]
    assert regions["enhancing_tumour"][0].tolist() == [False, False, False, True]
    assert regions["enhancing_tumour"][1].tolist() == [False, False, False, True]


def test_empty_region_handling_is_explicit():
    empty = np.zeros(4, dtype=bool)
    nonempty = np.array([True, False, False, False])
    both_empty = dice_result(empty, empty)
    one_empty = dice_result(empty, nonempty)
    assert both_empty["dice"] is None
    assert both_empty["status"] == "not_applicable_both_empty"
    assert one_empty["dice"] == 0.0
    assert one_empty["status"] == "one_empty"
