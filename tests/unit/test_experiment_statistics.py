import pytest

from backend.experiments.statistics import holm_adjust, paired_wilcoxon_summary


def test_holm_adjusts_and_preserves_input_order() -> None:
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([None, 0.2]) == [None, 0.2]


def test_paired_summary_uses_conditions_and_returns_effect_ci_and_p_value() -> None:
    result = paired_wilcoxon_summary([1, 2, 3, 4], [2, 3, 4, 5], seed=7)

    assert result["n_pairs"] == 4
    assert result["mean_paired_difference"] == 1.0
    assert result["rank_biserial_effect"] == 1.0
    assert result["ci95_mean_difference_low"] == 1.0
    assert result["ci95_mean_difference_high"] == 1.0
    assert 0 <= result["p_value"] <= 1


def test_equal_pairs_are_not_reported_as_evidence_of_difference() -> None:
    result = paired_wilcoxon_summary([1, 2, 3], [1, 2, 3])

    assert result["status"] == "no_nonzero_differences"
    assert result["p_value"] == 1.0


def test_paired_summary_rejects_unpaired_or_nonfinite_inputs() -> None:
    with pytest.raises(ValueError, match="equal paired"):
        paired_wilcoxon_summary([1, 2], [1])
    with pytest.raises(ValueError, match="finite"):
        paired_wilcoxon_summary([1, float("nan")], [1, 2])
