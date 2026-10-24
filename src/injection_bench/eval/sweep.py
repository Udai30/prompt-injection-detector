"""Threshold sweep for detector C and the operating-point rule (FR-7, TRD §5, M3.1).

The threshold is chosen on **validation only**: the highest-recall point whose false-positive rate
on validation benign prompts is at most ``MAX_FPR`` (ties go to the higher, more conservative
threshold). Test and hard negatives are only ever evaluated at the threshold chosen here.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from injection_bench.eval import metrics

MAX_FPR: Final = 0.02
GRID: Final = tuple(round(i / 100, 2) for i in range(1, 100))


@dataclass(frozen=True)
class SweepPoint:
    split: str
    threshold: float
    recall: float | None
    fpr: float | None
    precision: float | None


def read_scores(results_path: Path) -> tuple[list[bool], list[float]]:
    """Gold labels and scores of the non-error rows of a run's ``results.jsonl``."""
    gold: list[bool] = []
    scores: list[float] = []
    with results_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["status"] == "error" or row["score"] is None:
                continue
            gold.append(bool(row["gold"]["is_injection"]))
            scores.append(float(row["score"]))
    return gold, scores


def sweep(
    split: str, gold: Sequence[bool], scores: Sequence[float], grid: Sequence[float] = GRID
) -> list[SweepPoint]:
    points: list[SweepPoint] = []
    for threshold in grid:
        c = metrics.confusion(gold, [s >= threshold for s in scores])
        points.append(
            SweepPoint(split, threshold, metrics.recall(c), metrics.fpr(c), metrics.precision(c))
        )
    return points


def choose_operating_point(
    validation: Sequence[SweepPoint], max_fpr: float = MAX_FPR
) -> SweepPoint:
    """Max recall subject to FPR <= ``max_fpr`` on validation; highest threshold among ties."""
    admissible = [
        p for p in validation if p.fpr is not None and p.recall is not None and p.fpr <= max_fpr
    ]
    if not admissible:
        raise ValueError(f"no threshold keeps validation FPR <= {max_fpr:.0%}")
    best_recall = max(p.recall for p in admissible if p.recall is not None)
    return max((p for p in admissible if p.recall == best_recall), key=lambda p: p.threshold)


def write_sweep_csv(points: Sequence[SweepPoint], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["split", "threshold", "recall", "fpr", "precision"])
        for p in points:
            writer.writerow(
                [p.split, p.threshold]
                + ["" if v is None else f"{v:.4f}" for v in (p.recall, p.fpr, p.precision)]
            )


def write_operating_point(
    point: SweepPoint, path: Path, *, rule: str, extra: dict[str, Any] | None = None
) -> None:
    payload = {"rule": rule, "chosen_on": "validation", **asdict(point), **(extra or {})}
    path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")
