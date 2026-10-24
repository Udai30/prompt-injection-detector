"""Typer command-line interface: ``uv run injection_bench --help``.

Command groups are registered here; their commands are added by the tasks that own them
(IMPLEMENTATION_PLAN.md). Keep this module free of import-time side effects so ``--help``
works without a ``.env`` file.
"""

from __future__ import annotations

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


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
