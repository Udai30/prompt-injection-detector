"""Threshold sweep and the validation-only operating-point rule."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from injection_bench.eval import sweep

GOLD = [True] * 5 + [False] * 5
SCORES = [0.95, 0.9, 0.8, 0.6, 0.3, 0.7, 0.2, 0.1, 0.1, 0.05]


def test_sweep_trades_recall_for_fpr_monotonically() -> None:
    points = sweep.sweep("validation", GOLD, SCORES)
    recalls = [p.recall for p in points if p.recall is not None]
    fprs = [p.fpr for p in points if p.fpr is not None]
    assert recalls == sorted(recalls, reverse=True) and fprs == sorted(fprs, reverse=True)
    at_50 = next(p for p in points if p.threshold == 0.5)
    assert (at_50.recall, at_50.fpr) == (0.8, 0.2)


def test_operating_point_is_max_recall_under_the_fpr_cap_highest_threshold_on_ties() -> None:
    points = sweep.sweep("validation", GOLD, SCORES)
    chosen = sweep.choose_operating_point(points, max_fpr=0.0)
    assert chosen.recall == 0.6 and chosen.fpr == 0.0
    assert chosen.threshold == 0.8  # highest threshold that still yields recall 0.6
    loose = sweep.choose_operating_point(points, max_fpr=0.2)
    assert loose.recall == 1.0 and loose.threshold == 0.3


def test_no_admissible_threshold_is_an_error() -> None:
    points = sweep.sweep("validation", [True, False], [0.4, 0.4], grid=[0.1, 0.5])
    with pytest.raises(ValueError, match="no threshold"):
        sweep.choose_operating_point([points[0]], max_fpr=0.0)


def test_read_scores_skips_error_rows(tmp_path: Path) -> None:
    rows = [
        {"status": "pass", "score": 0.9, "gold": {"is_injection": True}},
        {"status": "error", "score": None, "gold": {"is_injection": False}},
        {"status": "fail", "score": 0.7, "gold": {"is_injection": False}},
    ]
    path = tmp_path / "results.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert sweep.read_scores(path) == ([True, False], [0.9, 0.7])


def test_csv_and_operating_point_files(tmp_path: Path) -> None:
    points = sweep.sweep("validation", GOLD, SCORES, grid=[0.5])
    sweep.write_sweep_csv(points, tmp_path / "s.csv")
    assert (tmp_path / "s.csv").read_text(encoding="utf-8").splitlines() == [
        "split,threshold,recall,fpr,precision",
        "validation,0.5,0.8000,0.2000,0.8000",
    ]
    sweep.write_operating_point(points[0], tmp_path / "op.json", rule="r")
    saved = json.loads((tmp_path / "op.json").read_text(encoding="utf-8"))
    assert saved["chosen_on"] == "validation" and saved["threshold"] == 0.5
