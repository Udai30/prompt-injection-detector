"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from injection_bench.config import Settings, get_settings


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Opt-in markers (live Ollama, hosted Groq, downloaded weights) run only when selected
    explicitly with ``-m <marker>`` (they still skip individually when a key is missing)."""
    selected = config.getoption("markexpr", "") or ""
    for marker in ("live", "hosted", "models"):
        if marker in selected:
            continue
        skip = pytest.mark.skip(reason=f"opt-in test; run with `uv run pytest -m {marker}`")
        for item in items:
            if item.get_closest_marker(marker):
                item.add_marker(skip)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[pytest.MonkeyPatch]:
    """Isolate a test from the developer's real environment and ``.env`` file.

    Removes every variable ``Settings`` reads, runs from an empty temp directory (so no
    ``.env`` is found) and clears the cached settings before and after.
    """
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()
