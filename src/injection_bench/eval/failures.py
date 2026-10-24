"""Failure export for hand-labelling: misses and false alarms of every finished run (PRD S1.4).

``failure_label`` is a *draft* cause from simple heuristics; the human confirms or corrects it in
``reports/failures.csv`` (``failure_label``, ``note``, ``fixed_by`` stay editable). Texts are
public deepset prompts or the project's own hard negatives, so writing them out is safe.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from injection_bench.core.types import Case

LONG_TEXT: Final = 300
EXCERPT: Final = 200
COLUMNS: Final = [
    "run_id",
    "case_id",
    "detector",
    "variant",
    "subset",
    "kind",
    "language",
    "score",
    "missed_by_all",
    "failure_label",
    "note",
    "fixed_by",
    "text",
]


def draft_label(case: Case, kind: str, categories: Mapping[str, str]) -> str:
    """Heuristic first guess at the cause; deliberately coarse."""
    if kind == "false_alarm":
        return f"benign_lookalike:{categories.get(case.id, 'deepset')}"
    if case.language != "en":
        return f"non_english:{case.language}"
    if len(case.text) > LONG_TEXT:
        return "attack_inside_long_text"
    return "no_known_trigger_phrase"


def collect(
    runs_dir: Path,
    cases: Mapping[str, Mapping[str, Case]],
    categories: Mapping[str, str],
) -> list[dict[str, str]]:
    """``cases`` maps subset -> case id -> Case. Returns one row per failed case per run."""
    failed_by: dict[tuple[str, str], set[str]] = defaultdict(set)
    seen_by: dict[tuple[str, str], set[str]] = defaultdict(set)
    pending: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for summary_path in sorted(runs_dir.glob("*/summary.json")):
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        subset = summary["dataset_split"]
        results = summary_path.parent / "results.jsonl"
        for line in results.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "error":
                continue
            seen_by[(subset, row["case_id"])].add(summary["detector"])
            if row["status"] == "fail":
                failed_by[(subset, row["case_id"])].add(summary["detector"])
                pending.append((summary, row, subset))
    out: list[dict[str, str]] = []
    for summary, row, subset in pending:
        case = cases[subset][row["case_id"]]
        kind = "miss" if case.is_injection else "false_alarm"
        key = (subset, case.id)
        everyone = failed_by[key] == seen_by[key] and len(seen_by[key]) > 1
        out.append(
            {
                "run_id": summary["run_id"],
                "case_id": case.id,
                "detector": summary["detector"],
                "variant": summary["variant"],
                "subset": subset,
                "kind": kind,
                "language": case.language,
                "score": f"{row['score']:.3f}",
                "missed_by_all": "yes" if everyone and kind == "miss" else "",
                "failure_label": draft_label(case, kind, categories),
                "note": "",
                "fixed_by": "",
                "text": " ".join(case.text.split())[:EXCERPT],
            }
        )
    return out


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
