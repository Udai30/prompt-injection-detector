"""Opt-in live checks: `uv run pytest -m live` (Ollama) and `-m hosted` (Groq key)."""

from __future__ import annotations

import os
import socket

import pytest
from typer.testing import CliRunner

from injection_bench import cli


def _ollama_up() -> bool:
    try:
        with socket.create_connection(("localhost", 11434), timeout=1):
            return True
    except OSError:
        return False


@pytest.mark.live
@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
def test_ping_answers_from_local_ollama_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROFILE", "local")
    result = CliRunner().invoke(cli.app, ["llm", "ping"])
    assert result.exit_code == 0, result.output
    assert "ollama-qwen3-4b" in result.output


@pytest.mark.hosted
@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_ping_answers_from_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROFILE", "hosted")
    result = CliRunner().invoke(cli.app, ["llm", "ping"])
    assert result.exit_code == 0, result.output
    assert "groq-oss-20b" in result.output
