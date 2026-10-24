"""Hard-negative set: schema, validator and coverage report (FR-2, TRD §4.2, BACKEND_SCHEMA §1.2).

The set is benign prompts that *look* suspicious. It is written (by the human, from agent-drafted
candidates) before any detector runs on it and is never used for training or tuning. The agent only
ever writes ``hard_negatives.draft.jsonl``; ``hard_negatives.jsonl`` holds rows the human accepted
(``author: udai``).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from injection_bench.core.types import Case

FINAL_NAME: Final = "hard_negatives.jsonl"
DRAFT_NAME: Final = "hard_negatives.draft.jsonl"
MAX_CHARS: Final = 1_000
MIN_CHARS: Final = 10
TARGET_PER_CATEGORY: Final = 15
FINAL_AUTHOR: Final = "udai"
DRAFT_AUTHOR: Final = "claude-draft"

Category = Literal[
    "meta_questions",
    "media_instructions",
    "quoted_errors",
    "code_role_keys",
    "security_education",
    "benign_roleplay",
    "translation_imperative",
    "support_escalation",
]
CATEGORIES: Final[tuple[str, ...]] = (
    "meta_questions",
    "media_instructions",
    "quoted_errors",
    "code_role_keys",
    "security_education",
    "benign_roleplay",
    "translation_imperative",
    "support_escalation",
)
_ID_RE: Final = re.compile(r"^hn-\d{4}$")


class HardNegative(BaseModel):
    """One record of ``data_own/hard_negatives.jsonl``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=_ID_RE.pattern)
    text: str = Field(min_length=MIN_CHARS, max_length=MAX_CHARS)
    category: Category
    why_tricky: str = Field(min_length=3, max_length=200)
    author: str
    created: date


def normalise(text: str) -> str:
    """Case-, accent- and whitespace-insensitive key used to catch duplicates."""
    folded = unicodedata.normalize("NFKD", text).casefold()
    return re.sub(r"\W+", " ", folded).strip()


def load(path: Path) -> tuple[list[HardNegative], list[str]]:
    """Parse a JSONL file; returns (valid records, problems with line numbers)."""
    records: list[HardNegative] = []
    problems: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(HardNegative.model_validate_json(line))
            except ValidationError as exc:
                detail = "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                    for e in exc.errors(include_input=False, include_url=False)[:3]
                )
                problems.append(f"line {number}: {detail}")
    return records, problems


def validate(records: list[HardNegative], *, final: bool) -> list[str]:
    """Cross-record checks: duplicate ids/texts, and (for the final file) the human author."""
    problems: list[str] = []
    seen_ids: set[str] = set()
    seen_texts: dict[str, str] = {}
    for record in records:
        if record.id in seen_ids:
            problems.append(f"{record.id}: duplicate id")
        seen_ids.add(record.id)
        key = normalise(record.text)
        if key in seen_texts:
            problems.append(f"{record.id}: duplicate text of {seen_texts[key]}")
        seen_texts.setdefault(key, record.id)
        allowed = {FINAL_AUTHOR} if final else {FINAL_AUTHOR, DRAFT_AUTHOR}
        if record.author not in allowed:
            problems.append(f"{record.id}: author '{record.author}' not in {sorted(allowed)}")
    return problems


def coverage(records: list[HardNegative]) -> dict[str, int]:
    """Prompts per category (every category listed, zero included)."""
    counts: Counter[str] = Counter(str(r.category) for r in records)
    return {category: counts.get(category, 0) for category in CATEGORIES}


def coverage_gaps(counts: dict[str, int], target: int = TARGET_PER_CATEGORY) -> list[str]:
    return [c for c, n in counts.items() if n < target]


def to_cases(records: list[HardNegative]) -> list[Case]:
    """Hard negatives as evaluation cases: all benign, English."""
    return [
        Case(
            id=r.id,
            text=r.text,
            is_injection=False,
            language="en",
            source="hard_negative",
            split="hard_negative",
        )
        for r in records
    ]


def resolve_path(directory: Path) -> tuple[Path, bool]:
    """(path, is_final): the human-accepted file when it exists, else the agent draft."""
    final = directory / FINAL_NAME
    if final.exists():
        return final, True
    return directory / DRAFT_NAME, False


def coverage_markdown(records: list[HardNegative], *, final: bool) -> str:
    counts = coverage(records)
    lines = [
        "# Hard-negative coverage",
        "",
        f"Source: `{FINAL_NAME if final else DRAFT_NAME}` "
        + ("(human-accepted)" if final else "(**agent draft, not yet accepted by the human**)"),
        f"Total: **{len(records)}** prompts, target >= {TARGET_PER_CATEGORY} per category",
        "",
        "| Category | Prompts | Meets target |",
        "|---|---:|:---:|",
    ]
    lines += [
        f"| {category} | {n} | {'yes' if n >= TARGET_PER_CATEGORY else 'no'} |"
        for category, n in counts.items()
    ]
    return "\n".join(lines) + "\n"
