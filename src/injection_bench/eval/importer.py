"""``cli import-predictions``: Kaggle notebook scores become normal run directories (TRD §S4).

The notebook writes ``predictions.jsonl`` with a ``{case_id, split, score}`` object per
validation/test case (never hard negatives: those are scored locally). Importing makes the GPU-
trained detector C appear in the same results table as the CPU and API variants, and keeps the raw
scores so the threshold sweep (M3.1) needs no re-run.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from injection_bench.core.types import Case, Evidence, Verdict
from injection_bench.eval import runner

PREDICTION_SPLITS = ("validation", "test")


class PredictionsError(ValueError):
    """The predictions file does not match the fixed splits."""


def load_scores(path: Path) -> dict[str, dict[str, float]]:
    """Read ``predictions.jsonl`` into ``{split: {case_id: score}}``."""
    scores: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                split, case_id, score = str(row["split"]), str(row["case_id"]), float(row["score"])
            except (ValueError, KeyError, TypeError):
                raise PredictionsError(
                    f"{path.name} line {number}: not a valid prediction"
                ) from None
            if not 0.0 <= score <= 1.0:
                raise PredictionsError(f"{path.name} line {number}: score {score} outside [0, 1]")
            scores.setdefault(split, {})[case_id] = score
    return scores


def verdict_for(score: float, threshold: float) -> Verdict:
    return Verdict(
        detector="C",
        is_injection=score >= threshold,
        score=score,
        threshold=threshold,
        latency_ms=0.0,
        list_cost_usd=Decimal(0),
        evidence=Evidence(),
    )


def import_split(
    cases: Sequence[Case],
    scores: dict[str, float],
    *,
    split: str,
    variant: str,
    threshold: float,
    runs_dir: Path,
    notebook: str,
    revision: str = "",
    hn_status: runner.HnStatus = "n/a",
    source: str = "kaggle",
) -> dict[str, Any]:
    """Write one run directory for ``split``; every case must have a score."""
    missing = [c.id for c in cases if c.id not in scores]
    extra = sorted(set(scores) - {c.id for c in cases})
    if missing or extra:
        raise PredictionsError(
            f"{split}: {len(missing)} case(s) without a score, {len(extra)} unknown id(s)"
            " (are the splits the same as the notebook's?)"
        )
    config = runner.RunConfig(
        detector="C",
        variant=variant,
        subset=split,
        threshold=threshold,
        params={"source": source, "notebook": notebook},
        hn_status=hn_status,
    )
    rid = runner.run_id_for(config, [c.id for c in cases])
    run_dir = runs_dir / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    rows = [
        runner.make_row(case, verdict_for(scores[case.id], threshold), None, None) for case in cases
    ]
    with (run_dir / "results.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return runner.finish_run(
        config,
        rid,
        run_dir,
        rows,
        started,
        dataset_revision=revision,
        extra_manifest={"kaggle": {"notebook": notebook, "latency": "not measured on Kaggle"}},
    )
