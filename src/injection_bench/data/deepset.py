"""deepset/prompt-injections: pinned download, language tags and fixed splits (FR-1, M1.1).

Raw parquet files are fetched only by ``cli data prepare`` (never at import time or app start).
``data/deepset/{train,validation,test}.jsonl`` and ``splits.json`` are the fixed splits every
detector is judged on; validation is carved from the original train split (15 %, stratified by
label, seed 42) and the original test split stays untouched until the final runs.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

import pandas as pd

from injection_bench.core.types import Case, Language

DATASET_ID: Final = "deepset/prompt-injections"
REVISION: Final = "4f61ecb038e9c3fb77e21034b22511b523772cdd"
LICENSE: Final = "apache-2.0"
SEED: Final = 42
VALIDATION_FRACTION: Final = 0.15
FILES: Final = {
    "train": "data/train-00000-of-00001-9564e8b05b4757ab.parquet",
    "test": "data/test-00000-of-00001-701d16158af87368.parquet",
}
SPLITS: Final = ("train", "validation", "test")

Downloader = Callable[[str], Path]
LanguageTagger = Callable[[str], Language]


def hf_downloader(dest: Path) -> Downloader:
    """Fetch one dataset file at the pinned revision into ``dest`` (explicit CLI action only)."""

    def download(filename: str) -> Path:
        from huggingface_hub import hf_hub_download  # noqa: PLC0415 - heavy, CLI-time only

        return Path(
            hf_hub_download(
                repo_id=DATASET_ID,
                filename=filename,
                repo_type="dataset",
                revision=REVISION,
                local_dir=dest / "raw",
            )
        )

    return download


def lingua_tagger() -> LanguageTagger:
    """Tag a text ``en`` / ``de`` / ``other`` with a lightweight offline detector."""
    from lingua import Language as L  # noqa: N817, PLC0415
    from lingua import LanguageDetectorBuilder  # noqa: PLC0415

    detector = LanguageDetectorBuilder.from_languages(
        L.ENGLISH, L.GERMAN, L.FRENCH, L.SPANISH, L.ITALIAN, L.PORTUGUESE
    ).build()

    def tag(text: str) -> Language:
        found = detector.detect_language_of(text)
        if found == L.ENGLISH:
            return "en"
        if found == L.GERMAN:
            return "de"
        return "other"

    return tag


def carve_validation(
    labels: Sequence[bool], fraction: float = VALIDATION_FRACTION, seed: int = SEED
) -> set[int]:
    """Indices (into ``labels``) held out for validation: stratified by label, seeded."""
    rng = random.Random(seed)  # noqa: S311 - reproducible split, not security
    held: set[int] = set()
    for label in (False, True):
        idx = [i for i, value in enumerate(labels) if value is label]
        rng.shuffle(idx)
        held.update(idx[: round(len(idx) * fraction)])
    return held


def _records(frame: pd.DataFrame, split: str, tag: LanguageTagger) -> list[Case]:
    return [
        Case(
            id=f"ds-{split}-{i:04d}",
            text=str(row["text"]),
            is_injection=bool(row["label"]),
            language=tag(str(row["text"])),
            source="deepset",
            split=split,
        )
        for i, (_, row) in enumerate(frame.iterrows())
    ]


def ids_hash(ids: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()[:16]


def write_jsonl(path: Path, cases: Sequence[Case]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(case.model_dump_json() + "\n")


def read_jsonl(path: Path) -> list[Case]:
    with path.open(encoding="utf-8") as handle:
        return [Case.model_validate_json(line) for line in handle if line.strip()]


def prepare(data_dir: Path, download: Downloader, tag: LanguageTagger) -> dict[str, Any]:
    """Build the three splits under ``data_dir/deepset`` and return the manifest."""
    out = data_dir / "deepset"
    original_train = pd.read_parquet(download(FILES["train"]))
    original_test = pd.read_parquet(download(FILES["test"]))

    held = carve_validation([bool(v) for v in original_train["label"]])
    keep = original_train.drop(index=list(held)).reset_index(drop=True)
    valid = original_train.loc[sorted(held)].reset_index(drop=True)
    frames = {"train": keep, "validation": valid, "test": original_test.reset_index(drop=True)}

    manifest: dict[str, Any] = {
        "dataset": DATASET_ID,
        "revision": REVISION,
        "license": LICENSE,
        "seed": SEED,
        "validation_fraction": VALIDATION_FRACTION,
        "splits": {},
    }
    for split, frame in frames.items():
        cases = _records(frame, split, tag)
        write_jsonl(out / f"{split}.jsonl", cases)
        manifest["splits"][split] = {
            "n": len(cases),
            "ids_hash": ids_hash([c.id for c in cases]),
            "ids": [c.id for c in cases],
            "languages": {c.id: c.language for c in cases},
        }
    (out / "splits.json").write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def load_split(data_dir: Path, split: str) -> list[Case]:
    if split not in SPLITS:
        raise ValueError(f"unknown split '{split}'; expected one of {', '.join(SPLITS)}")
    path = data_dir / "deepset" / f"{split}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `injection_bench data prepare` first")
    return read_jsonl(path)


def stats(data_dir: Path) -> list[dict[str, Any]]:
    """Label balance by language and split (rows of split, language, benign, injection)."""
    rows: list[dict[str, Any]] = []
    for split in SPLITS:
        counts: Counter[tuple[str, bool]] = Counter()
        for case in load_split(data_dir, split):
            counts[(case.language, case.is_injection)] += 1
        for language in ("en", "de", "other"):
            benign, attack = counts[(language, False)], counts[(language, True)]
            if benign or attack:
                rows.append(
                    {"split": split, "language": language, "benign": benign, "injection": attack}
                )
    return rows
