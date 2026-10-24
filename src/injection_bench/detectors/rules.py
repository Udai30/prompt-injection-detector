"""Detector A: regex/keyword rules with per-rule hit counting (FR-3, TRD §4.1).

The text is only ever matched against compiled patterns; it is never executed or forwarded.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from injection_bench.core.types import DetectorId, Evidence, Verdict

MAX_CHARS: Final = 20_000  # matching is linear, but cap pathological inputs anyway
DEFAULT_RULES_PATH: Final = Path("configs/rules.yaml")
DECISION_THRESHOLD: Final = 0.5


class RuleError(RuntimeError):
    """The rules file is missing or invalid."""


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    pattern: str = Field(min_length=1, max_length=600)
    note: str = Field(min_length=1)


class RuleFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int
    rules: list[Rule] = Field(min_length=1)


def load_rules(path: Path = DEFAULT_RULES_PATH) -> RuleFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        parsed = RuleFile.model_validate(raw)
    except (OSError, yaml.YAMLError) as exc:
        raise RuleError(f"cannot read {path}: {type(exc).__name__}") from None
    except ValidationError as exc:
        raise RuleError(f"invalid {path.name}: {exc.error_count()} error(s)") from None
    ids = [r.id for r in parsed.rules]
    if len(set(ids)) != len(ids):
        raise RuleError("duplicate rule ids")
    return parsed


class RuleDetector:
    """A: flags a text when any rule matches; score = 1 - 0.5**hits (0, .5, .75, ...)."""

    id: DetectorId = "A"
    name: str = "A: rules"

    def __init__(self, rules: RuleFile) -> None:
        self.version = rules.version
        try:
            self._compiled = [
                (r.id, re.compile(r.pattern, re.IGNORECASE | re.MULTILINE)) for r in rules.rules
            ]
        except re.error as exc:
            raise RuleError(f"bad regex: {exc}") from None
        self.hits: Counter[str] = Counter()

    @classmethod
    def from_path(cls, path: Path = DEFAULT_RULES_PATH) -> RuleDetector:
        return cls(load_rules(path))

    @property
    def rule_ids(self) -> list[str]:
        return [rule_id for rule_id, _ in self._compiled]

    def match(self, text: str) -> list[str]:
        clipped = text[:MAX_CHARS]
        return [rule_id for rule_id, regex in self._compiled if regex.search(clipped)]

    def score(self, texts: Sequence[str]) -> list[Verdict]:
        verdicts: list[Verdict] = []
        for text in texts:
            started = time.perf_counter()
            matched = self.match(text)
            self.hits.update(matched)
            verdicts.append(
                Verdict(
                    detector="A",
                    is_injection=bool(matched),
                    score=1 - 0.5 ** len(matched),
                    threshold=DECISION_THRESHOLD,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    evidence=Evidence(rules=tuple(matched)),
                )
            )
        return verdicts
