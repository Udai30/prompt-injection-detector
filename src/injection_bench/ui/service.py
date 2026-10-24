"""Demo back end: classify one pasted text with each available detector (APPFLOW, TRD §S7).

The text is only classified: it is never executed, never forwarded to a tool-using model and never
logged (only metadata leaves this module). Detector failures become a plain-language row, never a
stack trace or provider message.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from injection_bench.core.types import Detector

if TYPE_CHECKING:
    from injection_bench.config import Settings

MAX_CHARS: Final = 2_000
DetectorFactory = Callable[[], Detector]


@dataclass(frozen=True)
class Row:
    detector: str
    verdict: str
    score: str
    latency: str
    detail: str


class InputError(ValueError):
    """The pasted text is empty or too long (shown to the user as-is)."""


def validate(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise InputError("Paste some text to check.")
    if len(cleaned) > MAX_CHARS:
        raise InputError(f"Text is too long ({len(cleaned)} characters; the limit is {MAX_CHARS}).")
    return cleaned


def default_factories(settings: Settings, c_path: Path | None = None) -> dict[str, DetectorFactory]:
    """Factories for A, B, C, D; each builds lazily so a missing model only affects its own row."""
    from injection_bench.detectors.factory import build_detector  # noqa: PLC0415

    def make(letter: str, **kw: object) -> DetectorFactory:
        def build() -> Detector:
            return build_detector(letter, settings, **kw)[0]  # type: ignore[arg-type]

        return build

    return {
        "A: rules": make("A"),
        "B: Prompt Guard 2": make("B", model="protectai-deberta"),
        "C: fine-tuned": make("C", c_path=c_path),
        "D: LLM judge": make("D"),
    }


def check(
    text: str, factories: dict[str, DetectorFactory], cache: dict[str, Detector] | None = None
) -> tuple[list[Row], str]:
    """Run every detector on ``text``; returns the rows and a short request id."""
    cleaned = validate(text)
    request_id = uuid.uuid4().hex[:8]
    rows: list[Row] = []
    store = cache if cache is not None else {}
    for name, factory in factories.items():
        try:
            if name not in store:
                store[name] = factory()
            verdict = store[name].score([cleaned])[0]
        except Exception:
            rows.append(Row(name, "unavailable", "-", "-", f"not available (ref {request_id})"))
            continue
        detail = ", ".join(verdict.evidence.rules) or (verdict.evidence.reason or "")
        rows.append(
            Row(
                name,
                "INJECTION" if verdict.is_injection else "looks benign",
                f"{verdict.score:.2f}",
                f"{verdict.latency_ms:.0f} ms",
                detail,
            )
        )
    return rows, request_id


def as_table(rows: Sequence[Row]) -> list[list[str]]:
    return [[r.detector, r.verdict, r.score, r.latency, r.detail] for r in rows]
