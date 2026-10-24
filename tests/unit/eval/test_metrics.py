"""Metrics: confusion counts, rates, undefined cases and seeded bootstrap intervals."""

from __future__ import annotations

import math

import pytest

from injection_bench.eval import metrics

GOLD = [True, True, True, True, False, False, False, False]
PRED = [True, True, True, False, True, False, False, False]


def test_confusion_and_rates() -> None:
    c = metrics.confusion(GOLD, PRED)
    assert (c.tp, c.fp, c.tn, c.fn) == (3, 1, 3, 1)
    assert metrics.recall(c) == 0.75
    assert metrics.fpr(c) == 0.25
    assert metrics.precision(c) == 0.75
    assert metrics.f1(c) == 0.75


def test_rates_are_none_not_zero_when_the_class_is_absent() -> None:
    benign_only = metrics.confusion([False, False], [True, False])
    assert metrics.recall(benign_only) is None and metrics.fpr(benign_only) == 0.5
    attacks_only = metrics.confusion([True], [True])
    assert metrics.fpr(attacks_only) is None
    assert metrics.f1(metrics.confusion([False], [False])) is None


def test_length_mismatch_is_an_error() -> None:
    with pytest.raises(ValueError, match="lengths differ"):
        metrics.confusion([True], [True, False])


def test_bootstrap_interval_brackets_the_estimate_and_is_reproducible() -> None:
    first = metrics.estimate("recall", GOLD * 10, PRED * 10)
    again = metrics.estimate("recall", GOLD * 10, PRED * 10)
    assert first == again
    assert first.ci_low is not None and first.ci_high is not None
    assert first.ci_low <= 0.75 <= first.ci_high
    small = metrics.estimate("recall", GOLD, PRED)
    assert small.ci_low is not None and small.ci_high is not None
    assert small.ci_high - small.ci_low > first.ci_high - first.ci_low


def test_perfect_detector_has_a_degenerate_interval() -> None:
    est = metrics.estimate("recall", [True, True, False], [True, True, False])
    assert (est.value, est.ci_low, est.ci_high) == (1.0, 1.0, 1.0)


def test_percentile() -> None:
    assert metrics.percentile([1, 2, 3, 4, 5], 50) == 3.0
    nan = metrics.percentile([], 50)
    assert math.isnan(nan)
