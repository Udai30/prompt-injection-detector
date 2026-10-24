"""M1.1: splits are reproducible, stratified, disjoint and language-tagged (offline)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from injection_bench import cli
from injection_bench.data import deepset

runner = CliRunner()


def _tag(text: str) -> str:
    return "de" if text.startswith("Ignoriere") else "en"


def _frames(tmp_path: Path) -> deepset.Downloader:
    train = pd.DataFrame(
        {
            "text": [f"Ignoriere alles {i}" if i % 5 == 0 else f"hello {i}" for i in range(100)],
            "label": [i % 4 == 0 for i in range(100)],
        }
    )
    test = pd.DataFrame({"text": ["a", "Ignoriere b", "c", "d"], "label": [0, 1, 0, 1]})
    paths = {deepset.FILES["train"]: train, deepset.FILES["test"]: test}

    def download(filename: str) -> Path:
        path = tmp_path / Path(filename).name
        paths[filename].to_parquet(path)
        return path

    return download


def test_carve_validation_is_stratified_seeded_and_stable() -> None:
    labels = [i % 4 == 0 for i in range(200)]  # 50 attacks, 150 benign
    held = deepset.carve_validation(labels)
    assert held == deepset.carve_validation(labels)
    assert sum(labels[i] for i in held) == round(50 * 0.15)
    assert sum(not labels[i] for i in held) == round(150 * 0.15)


def test_prepare_writes_disjoint_splits_with_languages(tmp_path: Path) -> None:
    manifest = deepset.prepare(tmp_path, _frames(tmp_path), _tag)
    sizes = {s: manifest["splits"][s]["n"] for s in deepset.SPLITS}
    assert sizes == {"train": 85, "validation": 15, "test": 4}
    train = deepset.load_split(tmp_path, "train")
    valid = deepset.load_split(tmp_path, "validation")
    assert {c.text for c in train}.isdisjoint({c.text for c in valid})
    assert {c.language for c in train + valid} == {"en", "de"}
    assert all(c.source == "deepset" and c.split == "validation" for c in valid)
    again = deepset.prepare(tmp_path, _frames(tmp_path), _tag)
    assert again["splits"]["validation"]["ids_hash"] == manifest["splits"]["validation"]["ids_hash"]


def test_stats_counts_label_balance_by_language(tmp_path: Path) -> None:
    deepset.prepare(tmp_path, _frames(tmp_path), _tag)
    rows = deepset.stats(tmp_path)
    test_rows = {r["language"]: r for r in rows if r["split"] == "test"}
    assert test_rows["de"] == {"split": "test", "language": "de", "benign": 0, "injection": 1}
    assert sum(r["benign"] + r["injection"] for r in rows) == 104


def test_load_split_errors_are_actionable(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown split"):
        deepset.load_split(tmp_path, "dev")
    with pytest.raises(FileNotFoundError, match="data prepare"):
        deepset.load_split(tmp_path, "test")


def test_cli_stats_without_data_is_a_clear_error(
    clean_env: pytest.MonkeyPatch,
) -> None:
    result = runner.invoke(cli.app, ["data", "stats"])
    assert result.exit_code == 1 and "data prepare" in result.output


def test_lingua_tagger_tags_english_and_german() -> None:
    tag = deepset.lingua_tagger()
    assert tag("Please summarise the following article in three sentences.") == "en"
    assert tag("Bitte fasse den folgenden Artikel in drei Sätzen zusammen.") == "de"
