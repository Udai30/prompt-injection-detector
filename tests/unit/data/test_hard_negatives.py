"""M1.2: schema, validator, coverage and CLI for the hard-negative set (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from injection_bench import cli
from injection_bench.data import hard_negatives as hn

runner = CliRunner()
DATA_OWN = Path(__file__).resolve().parents[3] / "data_own"


def row(
    i: int, text: str, category: str = "meta_questions", author: str = "udai"
) -> dict[str, Any]:
    return {
        "id": f"hn-{i:04d}",
        "text": text,
        "category": category,
        "why_tricky": "looks like an attack",
        "author": author,
        "created": "2026-10-24",
    }


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_load_reports_schema_problems_with_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / hn.FINAL_NAME
    write(path, [row(1, "What is a system prompt?"), row(2, "short"), row(3, "x" * 1001)])
    records, problems = hn.load(path)
    assert len(records) == 1
    assert [p.split(":")[0] for p in problems] == ["line 2", "line 3"]


def test_unknown_category_and_bad_id_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / hn.FINAL_NAME
    write(path, [row(1, "What is a system prompt?", category="made_up")])
    bad = row(2, "What is a system prompt, really?")
    bad["id"] = "x-2"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(bad) + "\n")
    records, problems = hn.load(path)
    assert records == [] and len(problems) == 2


def test_validate_flags_duplicates_ignoring_case_and_punctuation() -> None:
    a = hn.HardNegative.model_validate(row(1, "What is a system prompt?"))
    b = hn.HardNegative.model_validate(row(2, "what is a SYSTEM prompt"))
    problems = hn.validate([a, b], final=True)
    assert problems == ["hn-0002: duplicate text of hn-0001"]


def test_final_file_needs_the_human_author_but_drafts_may_be_agent_written() -> None:
    draft = hn.HardNegative.model_validate(
        row(1, "What is a system prompt?", author="claude-draft")
    )
    assert hn.validate([draft], final=False) == []
    assert "author 'claude-draft'" in hn.validate([draft], final=True)[0]


def test_coverage_lists_every_category_and_gaps() -> None:
    records = [hn.HardNegative.model_validate(row(1, "What is a system prompt?"))]
    counts = hn.coverage(records)
    assert set(counts) == set(hn.CATEGORIES) and counts["meta_questions"] == 1
    assert hn.coverage_gaps(counts, target=1) == [c for c in hn.CATEGORIES if c != "meta_questions"]


def test_to_cases_are_all_benign_english_hard_negatives() -> None:
    cases = hn.to_cases([hn.HardNegative.model_validate(row(1, "What is a system prompt?"))])
    assert [(c.is_injection, c.language, c.source) for c in cases] == [
        (False, "en", "hard_negative")
    ]


def test_resolve_path_prefers_the_human_accepted_file(tmp_path: Path) -> None:
    assert hn.resolve_path(tmp_path) == (tmp_path / hn.DRAFT_NAME, False)
    (tmp_path / hn.FINAL_NAME).write_text("", encoding="utf-8")
    assert hn.resolve_path(tmp_path) == (tmp_path / hn.FINAL_NAME, True)


def test_cli_validate_and_coverage_on_a_draft(tmp_path: Path) -> None:
    write(
        tmp_path / hn.DRAFT_NAME,
        [row(1, "What is a system prompt?", author="claude-draft")],
    )
    ok = runner.invoke(cli.app, ["hn", "validate", "--dir", str(tmp_path)])
    assert ok.exit_code == 0 and "DRAFT set: 1 prompts" in ok.output
    out = tmp_path / "cov.md"
    cov = runner.invoke(cli.app, ["hn", "coverage", "--dir", str(tmp_path), "--write", str(out)])
    assert cov.exit_code == 0 and "agent draft" in out.read_text(encoding="utf-8")


def test_cli_validate_fails_on_problems(tmp_path: Path) -> None:
    write(tmp_path / hn.FINAL_NAME, [row(1, "What is a system prompt?", author="claude-draft")])
    result = runner.invoke(cli.app, ["hn", "validate", "--dir", str(tmp_path)])
    assert result.exit_code == 1 and "problem" in result.output


@pytest.mark.skipif(not (DATA_OWN / hn.DRAFT_NAME).exists(), reason="no draft file")
def test_committed_draft_is_valid_and_covers_every_category() -> None:
    records, problems = hn.load(DATA_OWN / hn.DRAFT_NAME)
    assert problems == [] and hn.validate(records, final=False) == []
    assert hn.coverage_gaps(hn.coverage(records)) == []
