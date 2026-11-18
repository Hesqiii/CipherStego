import numpy as np
import pytest

from backend.core.evaluation.rs_analysis import (
    _flip,
    _group_scores,
    _root_estimate,
    analyze_rs,
)


def test_f1_and_fminus1_are_signed_and_do_not_clip_boundary_values() -> None:
    values = np.array([[0, 1, 254, 255]], dtype=np.uint8)

    assert _flip(values, positive=True).tolist() == [[1, 0, 255, 254]]
    assert _flip(values, positive=False).tolist() == [[-1, 2, 253, 256]]


def test_rs_groups_use_disjoint_two_by_two_blocks_and_both_masks() -> None:
    channel = np.array([[10, 10], [10, 10]], dtype=np.uint8)
    m_score, minus_m_score, group_count = _group_scores(channel)

    assert group_count == 1
    assert m_score == 1.0
    assert minus_m_score == 1.0


def test_rs_discards_only_odd_border_pixels_for_grouping() -> None:
    channel = np.zeros((3, 5), dtype=np.uint8)

    _, _, group_count = _group_scores(channel)

    assert group_count == 2


def test_estimator_selects_smallest_absolute_root_and_rejects_out_of_range() -> None:
    valid = _root_estimate(0.2, 0.3, 0.25, -0.375)
    invalid = _root_estimate(0.0, 0.0, 0.0, 0.0)

    assert valid["status"] == "computed"
    assert valid["root"] == pytest.approx(-0.125)
    assert valid["p"] == pytest.approx(0.2)
    assert invalid["status"] == "unreliable"
    assert invalid["p"] is None


def test_rs_reports_each_channel_and_does_not_claim_unreliable_total() -> None:
    cover = np.random.default_rng(21).integers(0, 256, (64, 80, 3), dtype=np.uint8)
    stego = cover.copy()
    stego.reshape(-1)[:900] ^= 1

    result = analyze_rs(cover, stego, actual_embedded_bits=900)

    assert set(result["channels"]) == {"red", "green", "blue"}
    for channel in result["channels"].values():
        assert channel["status"] in {"computed", "unreliable"}
        if channel["corrected_fraction"] is not None:
            assert 0.0 <= channel["corrected_fraction"] <= 1.0
    if result["status"] != "computed":
        assert result["estimated_total_bits"] is None


def test_rs_rejects_different_shapes_and_negative_actual_count() -> None:
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="dimensi"):
        analyze_rs(image, np.zeros((8, 9, 3), dtype=np.uint8), 0)
    with pytest.raises(ValueError, match="nonnegatif"):
        analyze_rs(image, image, -1)
