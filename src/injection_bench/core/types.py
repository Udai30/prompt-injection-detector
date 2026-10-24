"""Shared domain contracts: labelled cases, detector verdicts and the Detector protocol
(TRD §4.1, BACKEND_SCHEMA §1)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["en", "de", "other"]
Source = Literal["deepset", "hard_negative"]
DetectorId = Literal["A", "B", "C", "D"]

_FROZEN = ConfigDict(extra="forbid", frozen=True)


class Case(BaseModel):
    """One labelled prompt. ``is_injection`` is the gold label (hard negatives are all False)."""

    model_config = _FROZEN

    id: str
    text: str
    is_injection: bool
    language: Language
    source: Source
    split: str


class Evidence(BaseModel):
    """What a detector says about its own decision: A's rule ids, D's one-line reason."""

    model_config = _FROZEN

    rules: tuple[str, ...] = ()
    reason: str | None = None


class Verdict(BaseModel):
    """A detector's output for one text. ``score`` is in [0, 1]; higher = more injection-like."""

    model_config = _FROZEN

    detector: DetectorId
    is_injection: bool
    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    latency_ms: float = Field(ge=0.0)
    tokens_in: int = 0
    tokens_out: int = 0
    list_cost_usd: Decimal = Decimal(0)
    evidence: Evidence = Evidence()
    schema_valid: bool | None = None  # D only: the model's reply matched the verdict schema


class Detector(Protocol):
    """Scores texts one by one; never acts on them (the texts are data, never instructions)."""

    id: DetectorId
    name: str

    def score(self, texts: Sequence[str]) -> list[Verdict]: ...
