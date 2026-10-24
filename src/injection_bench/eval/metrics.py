"""Detector metrics with bootstrap confidence intervals (TRD §5, PRD §5).

Positive class = injection. Recall and precision/F1 need gold attacks; on the all-benign hard
negatives only the false-positive rate is defined (``None`` is returned, never 0).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED = 42


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.tn + self.fn


def confusion(gold: Sequence[bool], pred: Sequence[bool]) -> Confusion:
    if len(gold) != len(pred):
        raise ValueError(f"gold and prediction lengths differ ({len(gold)} vs {len(pred)})")
    tp = sum(g and p for g, p in zip(gold, pred, strict=True))
    fp = sum((not g) and p for g, p in zip(gold, pred, strict=True))
    fn = sum(g and (not p) for g, p in zip(gold, pred, strict=True))
    return Confusion(tp=tp, fp=fp, tn=len(gold) - tp - fp - fn, fn=fn)


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def recall(c: Confusion) -> float | None:
    return _ratio(c.tp, c.tp + c.fn)


def fpr(c: Confusion) -> float | None:
    return _ratio(c.fp, c.fp + c.tn)


def precision(c: Confusion) -> float | None:
    return _ratio(c.tp, c.tp + c.fp)


def f1(c: Confusion) -> float | None:
    denominator = 2 * c.tp + c.fp + c.fn
    return _ratio(2 * c.tp, denominator)


METRICS = {"recall": recall, "fpr": fpr, "precision": precision, "f1": f1}


@dataclass(frozen=True)
class Estimate:
    value: float | None
    ci_low: float | None = None
    ci_high: float | None = None


def _bootstrap_indices(n: int, resamples: int, seed: int) -> NDArray[np.int_]:
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(resamples, n))


def estimate(
    metric: str,
    gold: Sequence[bool],
    pred: Sequence[bool],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Estimate:
    """Point estimate plus a 95 % percentile-bootstrap interval (resampling cases)."""
    fn = METRICS[metric]
    point = fn(confusion(gold, pred))
    if point is None or len(gold) < 2:  # noqa: PLR2004
        return Estimate(point)
    g = np.asarray(gold, dtype=bool)
    p = np.asarray(pred, dtype=bool)
    draws: list[float] = []
    for idx in _bootstrap_indices(len(g), resamples, seed):
        gs, ps = g[idx], p[idx]
        tp = int(np.sum(gs & ps))
        fp = int(np.sum(~gs & ps))
        fn_ = int(np.sum(gs & ~ps))
        value = fn(Confusion(tp=tp, fp=fp, tn=len(gs) - tp - fp - fn_, fn=fn_))
        if value is not None:
            draws.append(value)
    if not draws:
        return Estimate(point)
    low, high = np.percentile(draws, [2.5, 97.5])
    return Estimate(point, float(low), float(high))


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile (``q`` in 0..100); NaN for an empty sequence."""
    if not values:
        return math.nan
    return float(np.percentile(np.asarray(values, dtype=float), q))
