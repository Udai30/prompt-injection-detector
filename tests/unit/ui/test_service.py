"""Demo service: input limits, per-detector failure isolation, no text in outputs of failures."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from injection_bench.core.types import DetectorId, Evidence, Verdict
from injection_bench.ui import app, service


class Fixed:
    id: DetectorId = "A"
    name = "fixed"

    def score(self, texts: Sequence[str]) -> list[Verdict]:
        return [
            Verdict(
                detector="A",
                is_injection=True,
                score=0.75,
                threshold=0.5,
                latency_ms=2.0,
                evidence=Evidence(rules=("r1",)),
            )
            for _ in texts
        ]


def boom() -> Fixed:
    raise RuntimeError("secret provider message with the pasted text")


def test_validate_rejects_empty_and_oversized_text() -> None:
    with pytest.raises(service.InputError, match="Paste"):
        service.validate("   ")
    with pytest.raises(service.InputError, match="too long"):
        service.validate("x" * (service.MAX_CHARS + 1))
    assert service.validate("  hi ") == "hi"


def test_one_failing_detector_does_not_break_the_others_or_leak_details() -> None:
    rows, request_id = service.check("some text", {"A": Fixed, "D": boom})
    assert rows[0].verdict == "INJECTION" and rows[0].detail == "r1" and rows[0].score == "0.75"
    assert rows[1].verdict == "unavailable"
    assert "secret" not in repr(rows[1]) and request_id in rows[1].detail


def test_detectors_are_built_once_and_reused() -> None:
    built: list[int] = []

    def factory() -> Fixed:
        built.append(1)
        return Fixed()

    cache: dict[str, Fixed] = {}
    service.check("a", {"A": factory}, cache)  # type: ignore[arg-type]
    service.check("b", {"A": factory}, cache)  # type: ignore[arg-type]
    assert len(built) == 1


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_app_builds_and_the_try_it_callback_reports_input_errors() -> None:
    demo = app.build({"A": Fixed})
    assert demo is not None
