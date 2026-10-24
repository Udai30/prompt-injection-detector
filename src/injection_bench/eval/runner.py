"""The eval runner (TRD §S4): one detector over one case subset, resumable, files only.

``runs/<run_id>/results.jsonl`` gets one line per case, appended as soon as the case finishes, and a
re-run skips finished case ids. A case-level exception becomes ``status = error``; it never aborts
the run. ``summary.json`` and ``manifest.json`` are written at the end.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from injection_bench.core.types import Case, Detector, DetectorId, Verdict
from injection_bench.eval import metrics

HnStatus = Literal["final", "draft", "n/a"]
PACKAGES = ("injection-bench", "pydantic", "numpy", "pandas", "litellm", "transformers", "torch")
PRIMARY_METRICS = ("recall", "fpr", "precision", "f1")


class RunConfig(BaseModel):
    """Names the detector variant, the subset and its parameters; the run id hashes it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: DetectorId
    variant: str = Field(min_length=1, max_length=80)
    subset: str  # validation | test | hard_negative
    threshold: float | None = None
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    hn_status: HnStatus = "n/a"
    limit: int | None = None  # first N cases (smoke runs); part of the id so it never mixes


def ids_hash(ids: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:16]


def run_id_for(config: RunConfig, ids: Sequence[str]) -> str:
    payload = config.model_dump_json() + "|" + ids_hash(ids)
    return f"{config.detector}-{config.subset}-{hashlib.sha256(payload.encode()).hexdigest()[:10]}"


def _git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None if out.returncode == 0 else None


def _packages() -> dict[str, str]:
    found: dict[str, str] = {}
    for name in PACKAGES:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            continue
    return found


def _read_done(path: Path) -> dict[str, dict[str, Any]]:
    done: dict[str, dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    done[row["case_id"]] = row
    return done


def make_row(
    case: Case, verdict: Verdict | None, error: str | None, wall_ms: float | None
) -> dict[str, Any]:
    gold = {"is_injection": case.is_injection, "language": case.language, "source": case.source}
    if verdict is None:
        return {
            "case_id": case.id,
            "status": "error",
            "score": None,
            "prediction": None,
            "gold": gold,
            "details": {"error": error},
            "latency_ms": wall_ms,
            "tokens_in": 0,
            "tokens_out": 0,
            "list_cost_usd": "0",
        }
    return {
        "case_id": case.id,
        "status": "pass" if verdict.is_injection == case.is_injection else "fail",
        "score": verdict.score,
        "prediction": verdict.model_dump(mode="json"),
        "gold": gold,
        "details": {
            "rules": list(verdict.evidence.rules),
            "reason": verdict.evidence.reason,
            "schema_valid": verdict.schema_valid,
        },
        "latency_ms": wall_ms,
        "tokens_in": verdict.tokens_in,
        "tokens_out": verdict.tokens_out,
        "list_cost_usd": str(verdict.list_cost_usd),
    }


def _metric_block(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] != "error"]
    gold = [bool(r["gold"]["is_injection"]) for r in ok]
    pred = [bool(r["prediction"]["is_injection"]) for r in ok]
    block: dict[str, Any] = {
        "n": len(ok),
        "n_attacks": sum(gold),
        "n_benign": len(gold) - sum(gold),
    }
    for name in PRIMARY_METRICS:
        undefined = not ok or (name in {"recall", "precision", "f1"} and not any(gold))
        est = metrics.Estimate(None) if undefined else metrics.estimate(name, gold, pred)
        block[name] = {"value": est.value, "ci_low": est.ci_low, "ci_high": est.ci_high}
    return block


def summarise(
    config: RunConfig, run_id: str, rows: Sequence[dict[str, Any]], started: str, finished: str
) -> dict[str, Any]:
    latencies = [float(r["latency_ms"]) for r in rows if r["latency_ms"] is not None]
    scored = [r for r in rows if r["status"] != "error"]
    cost = sum((Decimal(r["list_cost_usd"]) for r in rows), Decimal(0))
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_language[r["gold"]["language"]].append(r)
    return {
        "run_id": run_id,
        "detector": config.detector,
        "variant": config.variant,
        "dataset_split": config.subset,
        "hn_status": config.hn_status,
        "threshold": config.threshold,
        "sample_size": len(rows),
        "metrics": _metric_block(rows),
        "by_language": {lang: _metric_block(group) for lang, group in sorted(by_language.items())},
        "latency_ms": {
            "p50": metrics.percentile(latencies, 50) if latencies else None,
            "p95": metrics.percentile(latencies, 95) if latencies else None,
        },
        "tokens": {
            "in": sum(int(r["tokens_in"]) for r in rows),
            "out": sum(int(r["tokens_out"]) for r in rows),
        },
        "list_cost_usd_per_1k": str(cost / len(scored) * 1000) if scored else None,
        "n_errors": len(rows) - len(scored),
        "started_at": started,
        "finished_at": finished,
    }


def run(
    detector: Detector,
    cases: Sequence[Case],
    config: RunConfig,
    runs_dir: Path,
    *,
    dataset_name: str = "deepset/prompt-injections",
    dataset_revision: str = "",
    on_progress: Callable[[int, int], None] | None = None,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Run ``detector`` over ``cases`` (one at a time) and write the run directory."""
    import time  # noqa: PLC0415

    now = clock or time.perf_counter
    selected = list(cases[: config.limit] if config.limit else cases)
    ids = [c.id for c in selected]
    rid = run_id_for(config, ids)
    run_dir = runs_dir / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    results_path = run_dir / "results.jsonl"
    done = _read_done(results_path)
    started = datetime.now(UTC).isoformat(timespec="seconds")

    with results_path.open("a", encoding="utf-8", newline="\n") as handle:
        for position, case in enumerate(selected, start=1):
            if case.id in done:
                continue
            t0 = now()
            try:
                verdict: Verdict | None = detector.score([case.text])[0]
                error = None
            except Exception as exc:
                verdict, error = None, type(exc).__name__
            row = make_row(case, verdict, error, round((now() - t0) * 1000, 3))
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            done[case.id] = row
            if on_progress:
                on_progress(position, len(selected))

    rows = [done[i] for i in ids]
    return finish_run(
        config,
        rid,
        run_dir,
        rows,
        started,
        dataset_name=dataset_name,
        dataset_revision=dataset_revision,
    )


def finish_run(
    config: RunConfig,
    rid: str,
    run_dir: Path,
    rows: Sequence[dict[str, Any]],
    started: str,
    *,
    dataset_name: str = "deepset/prompt-injections",
    dataset_revision: str = "",
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write ``summary.json`` and ``manifest.json`` for finished ``rows`` and return the summary."""
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    summary = summarise(config, rid, rows, started, finished)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    manifest = {
        "run_id": rid,
        "resolved_config": config.model_dump(mode="json"),
        "dataset": {
            "name": dataset_name,
            "revision": dataset_revision,
            "split": config.subset,
            "ids_hash": ids_hash([str(r["case_id"]) for r in rows]),
        },
        "git_sha": _git_sha(),
        "packages": _packages(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    } | (extra_manifest or {})
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return summary
