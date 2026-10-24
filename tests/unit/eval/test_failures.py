"""Failure export: kinds, draft labels and the missed-by-all flag."""

from __future__ import annotations

import csv
from pathlib import Path

from injection_bench.core.types import Case
from injection_bench.eval import failures, runner
from tests.unit.eval.test_runner_report import KeywordDetector, case, config


def test_collect_marks_misses_false_alarms_and_missed_by_all(tmp_path: Path) -> None:
    cases = [
        case(1, "attack one", True),
        case(2, "sneaky", True),
        case(3, "Ignoriere alles", True, "de"),
        case(4, "an attack-free note about attack", False),
    ]
    runner.run(KeywordDetector(), cases, config(), tmp_path)
    runner.run(KeywordDetector(), cases, config(detector="B", variant="other"), tmp_path)
    by_id: dict[str, Case] = {c.id: c for c in cases}
    rows = failures.collect(tmp_path, {"test": by_id}, {})
    kinds = {(r["case_id"], r["detector"]): r["kind"] for r in rows}
    assert kinds[("c2", "A")] == "miss" and kinds[("c4", "A")] == "false_alarm"
    sneaky = next(r for r in rows if r["case_id"] == "c2")
    assert sneaky["missed_by_all"] == "yes" and sneaky["failure_label"] == "no_known_trigger_phrase"
    german = next(r for r in rows if r["case_id"] == "c3")
    assert german["failure_label"] == "non_english:de"
    out = tmp_path / "f.csv"
    failures.write_csv(rows, out)
    with out.open(encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == len(rows)


def test_false_alarm_label_uses_the_hard_negative_category() -> None:
    hn = case(1, "ignore the noise", False, source="hard_negative")
    assert failures.draft_label(hn, "false_alarm", {"c1": "media_instructions"}) == (
        "benign_lookalike:media_instructions"
    )
