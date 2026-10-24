"""The eval runner (resume, errors, summary) and the report tables, with a fake detector."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from injection_bench.core.types import Case, DetectorId, Evidence, Verdict
from injection_bench.eval import report, runner


class KeywordDetector:
    """Flags texts containing 'attack'; raises on 'boom'."""

    id: DetectorId = "A"
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def score(self, texts: Sequence[str]) -> list[Verdict]:
        out = []
        for text in texts:
            self.calls += 1
            if "boom" in text:
                raise RuntimeError("secret detail")
            hit = "attack" in text
            out.append(
                Verdict(
                    detector="A",
                    is_injection=hit,
                    score=1.0 if hit else 0.0,
                    threshold=0.5,
                    latency_ms=1.0,
                    tokens_in=3,
                    evidence=Evidence(rules=("r",) if hit else ()),
                )
            )
        return out


def case(i: int, text: str, bad: bool, lang: str = "en", source: str = "deepset") -> Case:
    return Case.model_validate(
        {
            "id": f"c{i}",
            "text": text,
            "is_injection": bad,
            "language": lang,
            "source": source,
            "split": "test",
        }
    )


CASES = [
    case(1, "attack one", True),
    case(2, "attack two", True, "de"),
    case(3, "sneaky", True),
    case(4, "hello", False),
    case(5, "an attack-free note about attack", False, "de"),
    case(6, "boom", False),
]


def config(**kw: Any) -> runner.RunConfig:
    base: dict[str, Any] = {"detector": "A", "variant": "fake", "subset": "test"}
    return runner.RunConfig.model_validate(base | kw)


def test_run_writes_files_and_counts_errors_without_aborting(tmp_path: Path) -> None:
    summary = runner.run(KeywordDetector(), CASES, config(), tmp_path)
    run_dir = tmp_path / summary["run_id"]
    assert {p.name for p in run_dir.iterdir()} == {"results.jsonl", "summary.json", "manifest.json"}
    lines = (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    assert [r["status"] for r in rows] == ["pass", "pass", "fail", "pass", "fail", "error"]
    assert rows[-1]["details"] == {"error": "RuntimeError"}  # exception text is never persisted
    assert summary["n_errors"] == 1
    m = summary["metrics"]
    assert m["n"] == 5 and m["recall"]["value"] == 2 / 3 and m["fpr"]["value"] == 0.5
    assert summary["by_language"]["de"]["n"] == 2
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset"]["split"] == "test"


def test_rerun_resumes_and_skips_finished_cases(tmp_path: Path) -> None:
    first = KeywordDetector()
    runner.run(first, CASES, config(), tmp_path)
    second = KeywordDetector()
    again = runner.run(second, CASES, config(), tmp_path)
    assert first.calls == 6 and second.calls == 0
    assert again["metrics"]["n"] == 5


def test_run_id_changes_with_config_and_cases() -> None:
    ids = [c.id for c in CASES]
    assert runner.run_id_for(config(), ids) == runner.run_id_for(config(), list(reversed(ids)))
    assert runner.run_id_for(config(), ids) != runner.run_id_for(config(threshold=0.4), ids)
    assert runner.run_id_for(config(), ids) != runner.run_id_for(config(), ids[:-1])


def test_limit_makes_a_distinct_smoke_run(tmp_path: Path) -> None:
    summary = runner.run(KeywordDetector(), CASES, config(limit=2), tmp_path)
    assert summary["sample_size"] == 2


def test_all_benign_subset_reports_fpr_only(tmp_path: Path) -> None:
    benign = [case(i, "hello", False, source="hard_negative") for i in range(3)]
    summary = runner.run(KeywordDetector(), benign, config(subset="hard_negative"), tmp_path)
    m = summary["metrics"]
    assert m["fpr"]["value"] == 0.0
    assert m["recall"]["value"] is None and m["precision"]["value"] is None


def test_report_builds_csv_and_markdown_and_flags_draft_rows(tmp_path: Path) -> None:
    runner.run(KeywordDetector(), CASES, config(), tmp_path / "runs")
    benign = [case(i, "attack?", False, source="hard_negative") for i in range(3)]
    runner.run(
        KeywordDetector(),
        benign,
        config(subset="hard_negative", hn_status="draft"),
        tmp_path / "runs",
    )
    rows = report.build(tmp_path / "runs", tmp_path / "reports")
    csv_text = (tmp_path / "reports" / "results.csv").read_text(encoding="utf-8")
    assert csv_text.splitlines()[0].startswith("run_id,detector,variant,subset,hn_status")
    assert any("[de]" in r["variant"] for r in rows)
    md = (tmp_path / "reports" / "results.md").read_text(encoding="utf-8")
    assert "hard_negative (DRAFT set)" in md and "[de]" not in md
