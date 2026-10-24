"""`report sweep`: threshold chosen on validation, applied to test (and local hard negatives)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from injection_bench import cli
from injection_bench.core.types import Case
from injection_bench.data import deepset

runner = CliRunner()


def make_cases(split: str, n: int = 20) -> list[Case]:
    return [
        Case(
            id=f"ds-{split}-{i:04d}",
            text=f"text {i}",
            is_injection=i < n // 2,
            language="en",
            source="deepset",
            split=split,
        )
        for i in range(n)
    ]


def score_for(case: Case) -> float:
    index = int(case.id.rsplit("-", 1)[1])
    # attacks 0..9 score 0.95..0.5; benign 10..19 score 0.4..0.05 -> perfectly separable at 0.5
    return 0.95 - 0.05 * index if case.is_injection else 0.4 - 0.035 * (index - 10)


@pytest.fixture
def workspace(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    clean_env.setenv("DATA_DIR", str(tmp_path / "data"))
    clean_env.chdir(tmp_path)  # cli writes runs/ and reports/ relative to the working directory
    rows = []
    for split in ("validation", "test"):
        cases = make_cases(split)
        deepset.write_jsonl(tmp_path / "data" / "deepset" / f"{split}.jsonl", cases)
        rows += [{"case_id": c.id, "split": split, "score": score_for(c)} for c in cases]
    keep = tmp_path / "data" / "c_scores"
    keep.mkdir(parents=True)
    (keep / "predictions.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    return tmp_path


def test_sweep_writes_curve_operating_point_chart_and_final_runs(workspace: Path) -> None:
    result = runner.invoke(cli.app, ["report", "sweep"])
    assert result.exit_code == 0, result.output
    assert "operating point" in result.output
    chosen = json.loads((workspace / "reports" / "operating_point.json").read_text("utf-8"))
    assert chosen["chosen_on"] == "validation" and chosen["fpr"] <= 0.02
    assert chosen["recall"] == 1.0 and chosen["test"]["recall"] == 1.0
    assert (workspace / "reports" / "threshold_sweep.csv").exists()
    assert (workspace / "reports" / "recall_vs_fpr.png").stat().st_size > 1_000
    runs = sorted(p.name for p in (workspace / "runs").iterdir())
    assert [r.split("-")[1] for r in runs] == ["test", "validation"]


def test_sweep_without_imported_scores_is_a_clear_error(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_env.setenv("DATA_DIR", str(tmp_path / "data"))
    clean_env.chdir(tmp_path)
    result = runner.invoke(cli.app, ["report", "sweep"])
    assert result.exit_code == 1 and "error:" in result.output
