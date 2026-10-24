"""`injection_bench llm ping` against FakeProvider (offline) and the CLI skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from injection_bench import __version__, cli
from injection_bench.llm.fake import FakeProvider, FakeReply

PROJECT_ROOT = Path(__file__).resolve().parents[2]

runner = CliRunner()


@pytest.fixture
def llm_env(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    clean_env.setenv("LLM_MODELS_PATH", str(PROJECT_ROOT / "configs" / "models.yaml"))
    clean_env.setenv("LLM_PRICING_PATH", str(PROJECT_ROOT / "configs" / "pricing.yaml"))
    clean_env.setenv("LLM_BUDGET_PATH", str(tmp_path / "budget.json"))
    clean_env.setenv("LLM_CACHE_DIR", str(tmp_path / "cache"))
    return clean_env


def test_help_and_version_need_no_environment(clean_env: pytest.MonkeyPatch) -> None:
    assert "llm" in runner.invoke(cli.app, ["--help"]).output
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0 and __version__ in result.output


def test_ping_without_flags_uses_role_judge_on_the_local_profile(
    llm_env: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider([FakeReply(text="pong", tokens_in=9, tokens_out=1)])
    llm_env.setattr(cli, "_provider_factory", lambda: provider)
    result = runner.invoke(cli.app, ["llm", "ping"])
    assert result.exit_code == 0, result.output
    assert "profile      local" in result.output
    assert "alias        ollama-qwen3-4b" in result.output
    assert "actual cost  $0" in result.output
    assert "pong" in result.output


def test_ping_hosted_profile_needs_a_key_and_reports_it_clearly(
    llm_env: pytest.MonkeyPatch,
) -> None:
    llm_env.setenv("LLM_PROFILE", "hosted")
    llm_env.setattr(cli, "_provider_factory", lambda: FakeProvider([]))
    result = runner.invoke(cli.app, ["llm", "ping"])
    assert result.exit_code == 1
    assert "error:" in result.output and "GROQ_API_KEY" in result.output


def test_ping_unknown_role_is_a_clear_error(llm_env: pytest.MonkeyPatch) -> None:
    result = runner.invoke(cli.app, ["llm", "ping", "--role", "nope"])
    assert result.exit_code == 1
    assert "unknown role" in result.output
