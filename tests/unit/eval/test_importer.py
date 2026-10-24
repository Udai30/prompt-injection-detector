"""import-predictions: Kaggle scores become run directories; mismatched splits fail loudly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from injection_bench import cli
from injection_bench.core.types import Case
from injection_bench.data import deepset
from injection_bench.eval import importer

runner = CliRunner()
NOTEBOOK = Path(__file__).resolve().parents[3] / "notebooks" / "finetune_injection.ipynb"


def cases(split: str, n: int = 4) -> list[Case]:
    return [
        Case(
            id=f"ds-{split}-{i:04d}",
            text=f"text {i}",
            is_injection=i % 2 == 0,
            language="en",
            source="deepset",
            split=split,
        )
        for i in range(n)
    ]


def write_predictions(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_load_scores_groups_by_split_and_validates(tmp_path: Path) -> None:
    file = tmp_path / "predictions.jsonl"
    write_predictions(
        file,
        [
            {"case_id": "a", "split": "test", "score": 0.9},
            {"case_id": "b", "split": "validation", "score": 0.1},
        ],
    )
    assert importer.load_scores(file) == {"test": {"a": 0.9}, "validation": {"b": 0.1}}
    write_predictions(file, [{"case_id": "a", "split": "test", "score": 1.5}])
    with pytest.raises(importer.PredictionsError, match="outside"):
        importer.load_scores(file)
    file.write_text("not json\n", encoding="utf-8")
    with pytest.raises(importer.PredictionsError, match="line 1"):
        importer.load_scores(file)


def test_import_split_writes_a_normal_run_directory(tmp_path: Path) -> None:
    test_cases = cases("test")
    scores = {c.id: (0.9 if c.is_injection else 0.1) for c in test_cases}
    summary = importer.import_split(
        test_cases,
        scores,
        split="test",
        variant="deberta-small@kaggle",
        threshold=0.5,
        runs_dir=tmp_path,
        notebook="nb",
    )
    assert summary["metrics"]["recall"]["value"] == 1.0
    assert summary["metrics"]["fpr"]["value"] == 0.0
    assert summary["latency_ms"] == {"p50": None, "p95": None}  # not measured on Kaggle
    run_dir = tmp_path / summary["run_id"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kaggle"]["notebook"] == "nb"


def test_missing_or_unknown_ids_are_rejected(tmp_path: Path) -> None:
    test_cases = cases("test")
    scores = {c.id: 0.5 for c in test_cases[:-1]} | {"ds-test-9999": 0.5}
    with pytest.raises(importer.PredictionsError, match="1 case"):
        importer.import_split(
            test_cases,
            scores,
            split="test",
            variant="v",
            threshold=0.5,
            runs_dir=tmp_path,
            notebook="nb",
        )


def test_cli_import_predictions_end_to_end(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    clean_env.setenv("DATA_DIR", str(tmp_path / "data"))
    for split in ("validation", "test"):
        deepset.write_jsonl(tmp_path / "data" / "deepset" / f"{split}.jsonl", cases(split))
    folder = tmp_path / "dl"
    folder.mkdir()
    write_predictions(
        folder / "predictions.jsonl",
        [
            {"case_id": c.id, "split": s, "score": 0.7 if c.is_injection else 0.2}
            for s in ("validation", "test")
            for c in cases(s)
        ],
    )
    result = runner.invoke(cli.app, ["import-predictions", str(folder)])
    assert result.exit_code == 0, result.output
    assert "validation: run C-validation-" in result.output
    assert (tmp_path / "data" / "c_scores" / "predictions.jsonl").exists()


def test_cli_import_predictions_reports_mismatched_splits(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_env.setenv("DATA_DIR", str(tmp_path / "data"))
    for split in ("validation", "test"):
        deepset.write_jsonl(tmp_path / "data" / "deepset" / f"{split}.jsonl", cases(split))
    folder = tmp_path / "dl"
    folder.mkdir()
    write_predictions(
        folder / "predictions.jsonl", [{"case_id": "x", "split": "test", "score": 0.5}]
    )
    result = runner.invoke(cli.app, ["import-predictions", str(folder)])
    assert result.exit_code == 1 and "without a score" in result.output


def test_kaggle_notebook_is_valid_secret_free_and_pins_the_local_splits() -> None:
    import ast  # noqa: PLC0415

    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
    for source in code:
        ast.parse(source)
    assert all(c["outputs"] == [] for c in nb["cells"] if c["cell_type"] == "code")
    text = "\n".join(code)
    assert deepset.REVISION in text and "hard_negative" not in text
    for token in ("api_key", "HF_TOKEN", "hf_token"):
        assert token not in text
    assert "assert ids_hash(ids) == EXPECTED_HASHES[name]" in text
