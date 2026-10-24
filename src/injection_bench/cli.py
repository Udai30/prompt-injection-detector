"""Typer command-line interface: ``uv run injection_bench --help``.

Command groups are registered here; their commands are added by the tasks that own them
(IMPLEMENTATION_PLAN.md). Keep this module free of import-time side effects so ``--help``
works without a ``.env`` file.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from injection_bench import __version__

if TYPE_CHECKING:
    from injection_bench.llm.providers import Provider

app = typer.Typer(
    name="injection_bench",
    help="Prompt-injection detector benchmark: data, detectors, runs and reports.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,  # locals may hold secrets
)

llm_app = typer.Typer(
    help="Call configured models through the LLM provider layer.", no_args_is_help=True
)
app.add_typer(llm_app, name="llm")

data_app = typer.Typer(help="Download and inspect the deepset splits.", no_args_is_help=True)
app.add_typer(data_app, name="data")

hn_app = typer.Typer(help="Hard-negative set: validate and report coverage.", no_args_is_help=True)
app.add_typer(hn_app, name="hn")

HN_DIR = Path("data_own")

eval_app = typer.Typer(help="Run detectors over the fixed case subsets.", no_args_is_help=True)
app.add_typer(eval_app, name="eval")
report_app = typer.Typer(help="Rebuild result tables and charts.", no_args_is_help=True)
app.add_typer(report_app, name="report")
models_app = typer.Typer(help="Download local model weights (explicit only).", no_args_is_help=True)
app.add_typer(models_app, name="models")

RUNS_DIR = Path("runs")
REPORTS_DIR = Path("reports")
SUBSETS = ("validation", "test", "hard_negative")

PING_PROMPT = "Reply with exactly one word: pong"
PING_MAX_TOKENS = 256
DEFAULT_ROLE = "judge"
_REPLY_PREVIEW_CHARS = 80


def _provider_factory() -> Provider | None:
    """Provider for CLI commands; ``None`` selects LiteLLM. Tests replace this."""
    return None


@app.callback(invoke_without_command=True)
def _root(
    version: Annotated[bool, typer.Option("--version", help="Print the version and exit.")] = False,
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit


@llm_app.command("ping")
def llm_ping(
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Alias from configs/models.yaml (overrides --role)."),
    ] = None,
    role: Annotated[
        str, typer.Option("--role", help="LLM role resolved through LLM_PROFILE.")
    ] = DEFAULT_ROLE,
) -> None:
    """Send one tiny request and print tokens, latency and cost (no cache).

    With no flags it pings role ``judge`` under the active profile (default ``local``).
    """
    import asyncio  # noqa: PLC0415 - keep `--help` free of the LLM stack

    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.llm import (  # noqa: PLC0415
        LLMError,
        LLMRequest,
        Message,
        build_client,
    )

    try:
        settings = get_settings()
        client = build_client(settings, cache=False, provider=_provider_factory())
        alias = model or client.registry.resolve(role, settings.llm_profile)
        response: Any = asyncio.run(
            client.complete(
                LLMRequest(
                    model_alias=alias,
                    messages=(Message(role="user", content=PING_PROMPT),),
                    max_tokens=PING_MAX_TOKENS,
                    data_origin="synthetic",
                )
            )
        )
    except (ConfigError, LLMError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None

    reply = " ".join(response.text.split())[:_REPLY_PREVIEW_CHARS] or "(empty)"
    cost = "n/a" if response.list_cost_usd is None else f"${response.list_cost_usd}"
    rows = [
        ("profile", settings.llm_profile),
        ("alias", response.model_alias),
        ("model", response.model),
        ("tokens", f"in={response.tokens_in} out={response.tokens_out}"),
        ("latency", f"{response.latency_ms} ms"),
        ("list cost", cost),
        ("actual cost", f"${response.actual_cost_usd}"),
        ("retries", str(response.retries)),
        ("reply", reply),
    ]
    for label, value in rows:
        typer.echo(f"{label:<12} {value}")


@data_app.command("prepare")
def data_prepare() -> None:
    """Download deepset/prompt-injections (pinned revision), tag language, write the splits."""
    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.data import deepset  # noqa: PLC0415

    try:
        data_dir = get_settings().data_dir
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    manifest = deepset.prepare(data_dir, deepset.hf_downloader(data_dir), deepset.lingua_tagger())
    typer.echo(f"{manifest['dataset']} @ {manifest['revision'][:8]}  licence {manifest['license']}")
    for split, info in manifest["splits"].items():
        typer.echo(f"{split:<11} n={info['n']:<4} ids_hash={info['ids_hash']}")
    typer.echo(f"written to {data_dir / 'deepset'}")


@data_app.command("stats")
def data_stats() -> None:
    """Label balance by language and split."""
    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.data import deepset  # noqa: PLC0415

    try:
        rows = deepset.stats(get_settings().data_dir)
    except (ConfigError, FileNotFoundError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"{'split':<11} {'lang':<6} {'benign':>6} {'injection':>9}")
    for row in rows:
        typer.echo(
            f"{row['split']:<11} {row['language']:<6} {row['benign']:>6} {row['injection']:>9}"
        )


def _hn_records(directory: Path) -> tuple[list[Any], bool, list[str]]:
    from injection_bench.data import hard_negatives as hn  # noqa: PLC0415

    path, final = hn.resolve_path(directory)
    if not path.exists():
        typer.echo(f"error: {path} not found", err=True)
        raise typer.Exit(code=1)
    records, problems = hn.load(path)
    return records, final, problems + hn.validate(records, final=final)


@hn_app.command("validate")
def hn_validate(
    directory: Annotated[Path, typer.Option("--dir", help="Folder with the JSONL files.")] = HN_DIR,
) -> None:
    """Check schema, lengths, categories, duplicates and authors (final file: author udai)."""
    records, final, problems = _hn_records(directory)
    typer.echo(f"{'final' if final else 'DRAFT'} set: {len(records)} prompts")
    for problem in problems:
        typer.echo(f"  problem: {problem}", err=True)
    if problems:
        raise typer.Exit(code=1)
    typer.echo("ok")


@hn_app.command("coverage")
def hn_coverage(
    directory: Annotated[Path, typer.Option("--dir", help="Folder with the JSONL files.")] = HN_DIR,
    write: Annotated[
        Path | None, typer.Option("--write", help="Also write the report to this markdown file.")
    ] = None,
) -> None:
    """Prompts per category against the target of 15."""
    from injection_bench.data import hard_negatives as hn  # noqa: PLC0415

    records, final, problems = _hn_records(directory)
    if problems:
        typer.echo(f"error: {len(problems)} validation problem(s); run `hn validate`", err=True)
        raise typer.Exit(code=1)
    report = hn.coverage_markdown(records, final=final)
    typer.echo(report)
    if write is not None:
        write.parent.mkdir(parents=True, exist_ok=True)
        write.write_text(report, encoding="utf-8", newline="\n")


def _load_cases(data_dir: Path, subset: str) -> tuple[list[Any], str]:
    """Cases of one subset and the hard-negative status ('final' | 'draft' | 'n/a')."""
    from injection_bench.data import deepset  # noqa: PLC0415
    from injection_bench.data import hard_negatives as hn  # noqa: PLC0415

    if subset == "hard_negative":
        path, final = hn.resolve_path(HN_DIR)
        if not path.exists():
            raise FileNotFoundError(f"{path} not found")
        records, problems = hn.load(path)
        problems += hn.validate(records, final=final)
        if problems:
            raise ValueError(
                f"{path.name} is invalid ({len(problems)} problem(s)); run `hn validate`"
            )
        return hn.to_cases(records), "final" if final else "draft"
    return deepset.load_split(data_dir, subset), "n/a"


@eval_app.command("run")
def eval_run(
    detector: Annotated[str, typer.Option("--detector", "-d", help="A, B, C or D.")],
    subset: Annotated[
        list[str] | None,
        typer.Option("--subset", "-s", help="validation, test or hard_negative (repeatable)."),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="D: LLM alias; B: prompt-guard-2 or protectai-deberta."),
    ] = None,
    threshold: Annotated[float | None, typer.Option(help="B/C decision threshold.")] = None,
    c_path: Annotated[
        Path | None, typer.Option("--c-path", help="C: directory of the fine-tuned model.")
    ] = None,
    limit: Annotated[int | None, typer.Option(help="Only the first N cases (smoke runs).")] = None,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="D: bypass the response cache (latency timing).")
    ] = False,
) -> None:
    """Run DETECTOR over the chosen subsets (default: validation, test, hard_negative)."""
    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.detectors.factory import build_detector  # noqa: PLC0415
    from injection_bench.detectors.hf_classifier import ModelUnavailableError  # noqa: PLC0415
    from injection_bench.detectors.rules import RuleError  # noqa: PLC0415
    from injection_bench.eval import runner  # noqa: PLC0415
    from injection_bench.llm import LLMError  # noqa: PLC0415

    detector = detector.upper()
    if detector not in {"A", "B", "C", "D"}:
        typer.echo("error: --detector must be A, B, C or D", err=True)
        raise typer.Exit(code=1)
    chosen = list(subset or SUBSETS)
    bad = [name for name in chosen if name not in SUBSETS]
    if bad:
        typer.echo(f"error: unknown subset {bad[0]}; use {', '.join(SUBSETS)}", err=True)
        raise typer.Exit(code=1)
    try:
        settings = get_settings()
        for name in chosen:
            cases, hn_status = _load_cases(settings.data_dir, name)
            config = runner.RunConfig(
                detector=detector,  # type: ignore[arg-type]
                variant="pending",
                subset=name,
                threshold=threshold,
                hn_status=hn_status,  # type: ignore[arg-type]
                limit=limit,
            )
            det, variant = build_detector(
                detector,  # type: ignore[arg-type]
                settings,
                model=model,
                threshold=threshold,
                c_path=c_path,
                provider=_provider_factory(),
                run_dir=RUNS_DIR,
                use_cache=not no_cache,
            )
            config = config.model_copy(update={"variant": variant})
            if no_cache:
                config = config.model_copy(
                    update={
                        "params": {"no_cache": True},
                        "variant": variant + " (timing, no cache)",
                    }
                )
            typer.echo(
                f"{variant} on {name} ({hn_status if name == 'hard_negative' else 'deepset'})"
            )

            def progress(done: int, total: int) -> None:
                if done % 10 == 0 or done == total:
                    typer.echo(f"  {done}/{total}")

            summary = runner.run(
                det, cases, config, RUNS_DIR, dataset_revision=_revision(), on_progress=progress
            )
            m = summary["metrics"]
            typer.echo(
                f"  run {summary['run_id']}: recall={m['recall']['value']} fpr={m['fpr']['value']} "
                f"errors={summary['n_errors']} p50={summary['latency_ms']['p50']} ms"
            )
    except (
        ConfigError,
        LLMError,
        ModelUnavailableError,
        RuleError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None


def _revision() -> str:
    from injection_bench.data import deepset  # noqa: PLC0415

    return deepset.REVISION


@app.command("import-predictions")
def import_predictions(
    directory: Annotated[
        Path, typer.Argument(help="Folder with the notebook's predictions.jsonl.")
    ],
    threshold: Annotated[
        float, typer.Option(help="Decision threshold for the imported run.")
    ] = 0.5,
    notebook: Annotated[str, typer.Option(help="Notebook name/version for the manifest.")] = (
        "finetune_injection"
    ),
) -> None:
    """Turn Kaggle notebook scores into run directories (validation and test) for detector C."""
    import shutil  # noqa: PLC0415

    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.eval import importer  # noqa: PLC0415

    path = directory / "predictions.jsonl"
    try:
        settings = get_settings()
        scores = importer.load_scores(path)
        for split in importer.PREDICTION_SPLITS:
            cases, _ = _load_cases(settings.data_dir, split)
            summary = importer.import_split(
                cases,
                scores.get(split, {}),
                split=split,
                variant="deberta-small@kaggle",
                threshold=threshold,
                runs_dir=RUNS_DIR,
                notebook=notebook,
                revision=_revision(),
            )
            m = summary["metrics"]
            typer.echo(
                f"{split}: run {summary['run_id']} "
                f"recall={m['recall']['value']} fpr={m['fpr']['value']}"
            )
        keep = settings.data_dir / "c_scores"
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, keep / "predictions.jsonl")  # raw scores for the threshold sweep
    except (ConfigError, importer.PredictionsError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None


@report_app.command("sweep")
def report_sweep(
    max_fpr: Annotated[
        float, typer.Option(help="Rule: max recall with validation FPR at most this.")
    ] = 0.02,
) -> None:
    """Sweep C on validation, choose the operating point there, report it on test + hard negatives.

    Needs the imported Kaggle scores (`data/c_scores/predictions.jsonl`). Hard negatives are only
    scored at the chosen threshold, from a local `eval run -d C` run.
    """
    import json  # noqa: PLC0415

    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.eval import charts, importer, report, sweep  # noqa: PLC0415

    try:
        settings = get_settings()
        scores = importer.load_scores(settings.data_dir / "c_scores" / "predictions.jsonl")
        cases = {name: _load_cases(settings.data_dir, name)[0] for name in ("validation", "test")}
        curves: dict[str, list[sweep.SweepPoint]] = {}
        for name, split_cases in cases.items():
            gold = [bool(c.is_injection) for c in split_cases]
            curves[name] = sweep.sweep(name, gold, [scores[name][c.id] for c in split_cases])
        chosen = sweep.choose_operating_point(curves["validation"], max_fpr)
        at_test = next(p for p in curves["test"] if p.threshold == chosen.threshold)
        rule = f"max recall with validation FPR <= {max_fpr:.0%}"
        sweep.write_sweep_csv(
            [*curves["validation"], *curves["test"]], REPORTS_DIR / "threshold_sweep.csv"
        )
        sweep.write_operating_point(
            chosen,
            REPORTS_DIR / "operating_point.json",
            rule=rule,
            extra={"test": at_test.__dict__},
        )
        variant = f"deberta-small@kaggle thr={chosen.threshold:.2f}"
        for name, split_cases in cases.items():
            importer.import_split(
                split_cases,
                scores[name],
                split=name,
                variant=variant,
                threshold=chosen.threshold,
                runs_dir=RUNS_DIR,
                notebook="finetune_injection",
                revision=_revision(),
            )
        hn_runs = sorted(
            RUNS_DIR.glob("C-hard_negative-*/results.jsonl"), key=lambda p: p.stat().st_mtime
        )
        if hn_runs:
            hn_cases, hn_status = _load_cases(settings.data_dir, "hard_negative")
            hn_scores = {
                json.loads(line)["case_id"]: json.loads(line)["score"]
                for line in hn_runs[-1].read_text(encoding="utf-8").splitlines()
                if line.strip() and json.loads(line)["score"] is not None
            }
            importer.import_split(
                hn_cases,
                hn_scores,
                split="hard_negative",
                variant=variant,
                threshold=chosen.threshold,
                runs_dir=RUNS_DIR,
                notebook="finetune_injection",
                revision=_revision(),
                hn_status=hn_status,  # type: ignore[arg-type]
                source="local",
            )
        test_runs = [
            s
            for s in report.load_summaries(RUNS_DIR)
            if s["dataset_split"] == "test" and s["detector"] in {"A", "B", "D"}
        ]
        charts.recall_vs_fpr(curves["test"], at_test, test_runs, REPORTS_DIR / "recall_vs_fpr.png")
    except (ConfigError, importer.PredictionsError, FileNotFoundError, KeyError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(
        f"operating point ({rule}): threshold={chosen.threshold:.2f} "
        f"validation recall={chosen.recall} fpr={chosen.fpr}; test recall={at_test.recall} "
        f"fpr={at_test.fpr}"
    )


@app.command("failures")
def failures() -> None:
    """Export misses and false alarms of all finished runs to reports/failures.csv for labelling."""
    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.data import hard_negatives as hn  # noqa: PLC0415
    from injection_bench.eval import failures as fail  # noqa: PLC0415

    try:
        data_dir = get_settings().data_dir
        cases = {name: {c.id: c for c in _load_cases(data_dir, name)[0]} for name in SUBSETS}
        path, _ = hn.resolve_path(HN_DIR)
        categories = {r.id: r.category for r in hn.load(path)[0]}
    except (ConfigError, FileNotFoundError, ValueError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    rows = fail.collect(RUNS_DIR, cases, categories)
    fail.write_csv(rows, REPORTS_DIR / "failures.csv")
    typer.echo(f"wrote {len(rows)} failure rows to {REPORTS_DIR / 'failures.csv'}")


@report_app.command("build")
def report_build() -> None:
    """Rebuild reports/results.csv and results.md from all finished runs."""
    from injection_bench.eval import report  # noqa: PLC0415

    rows = report.build(RUNS_DIR, REPORTS_DIR)
    typer.echo(f"wrote {len(rows)} rows to {REPORTS_DIR / 'results.csv'} and results.md")


@models_app.command("download")
def models_download(
    name: Annotated[str, typer.Argument(help="prompt-guard-2 or protectai-deberta.")],
) -> None:
    """Fetch a pinned model snapshot into the Hugging Face cache (prompt-guard-2 is gated)."""
    from injection_bench.config import ConfigError, get_settings  # noqa: PLC0415
    from injection_bench.detectors import hf_classifier as hf  # noqa: PLC0415

    if name not in hf.MODELS:
        typer.echo(f"error: unknown model '{name}'; known: {', '.join(hf.MODELS)}", err=True)
        raise typer.Exit(code=1)
    try:
        token = get_settings().hf_token
        path = hf.download(hf.MODELS[name], token.get_secret_value() if token else None)
    except (ConfigError, hf.ModelUnavailableError) as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"{name} @ {hf.MODELS[name].revision[:8]} -> {path}")


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
