"""Local CPU sequence classifiers for detectors B (Prompt Guard 2) and C (fine-tuned DeBERTa).

``transformers``/``torch`` are the optional ``models`` extra and are imported lazily, so the rest of
the package works without them. Weights are loaded from the local model cache only
(``local_files_only``): downloading is the explicit ``models download`` command's job, never an
import-time or app-start side effect. Texts longer than the model window are split into
overlapping chunks and the max injection probability is taken (TRD §3).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from injection_bench.core.types import DetectorId, Verdict

MAX_LENGTH: Final = 512
STRIDE: Final = 64
MAX_CHARS: Final = 20_000


class ModelUnavailableError(RuntimeError):
    """The optional dependencies or the local weights are missing; the message says what to run."""


@dataclass(frozen=True)
class ModelSpec:
    """A pinned Hub model and how to read its output."""

    key: str
    repo_id: str
    revision: str
    positive_index: int  # index of the 'injection' class in the logits
    gated: bool = False
    note: str = ""


# Pinned revisions (checked 2026-10-24). Prompt Guard 2 is gated: the human accepts its
# licence once.
MODELS: Final[dict[str, ModelSpec]] = {
    "prompt-guard-2": ModelSpec(
        key="prompt-guard-2",
        repo_id="meta-llama/Llama-Prompt-Guard-2-86M",
        revision="a8ded8e697ce7c355e395a0df51f94adb4a2fd27",
        positive_index=1,
        gated=True,
        note="LABEL_0 benign / LABEL_1 malicious; Llama 4 licence, gated",
    ),
    # Ungated stand-in (TRD §3): logged as a swap whenever it is used instead of Prompt Guard 2.
    "protectai-deberta": ModelSpec(
        key="protectai-deberta",
        repo_id="protectai/deberta-v3-base-prompt-injection-v2",
        revision="90c9989b1a342275dd0d1a95aad283c04e075671",
        positive_index=1,
        note="SAFE / INJECTION; Apache-2.0; stand-in for B",
    ),
}


def load_backend(spec: ModelSpec, *, source: str | None = None) -> tuple[Any, Any]:
    """Return ``(tokenizer, model)`` from the local cache (or a local directory ``source``)."""
    try:
        import torch  # noqa: F401, PLC0415
        from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: PLC0415
    except ImportError:
        raise ModelUnavailableError(
            "torch/transformers are not installed; run `uv sync --extra models`"
        ) from None
    target = source or spec.repo_id
    revision = None if source else spec.revision
    try:
        tokenizer = AutoTokenizer.from_pretrained(target, revision=revision, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            target, revision=revision, local_files_only=True
        )
    except OSError:
        raise ModelUnavailableError(
            f"model '{spec.key}' is not in the local cache; run "
            f"`uv run injection_bench models download {spec.key}`"
        ) from None
    model.eval()
    return tokenizer, model


class HFClassifierDetector:
    """Scores texts with a local sequence classifier; threshold applies to P(injection)."""

    def __init__(
        self,
        detector_id: DetectorId,
        name: str,
        tokenizer: Any,
        model: Any,
        *,
        positive_index: int = 1,
        threshold: float = 0.5,
    ) -> None:
        self.id: DetectorId = detector_id
        self.name = name
        self.threshold = threshold
        self._tokenizer = tokenizer
        self._model = model
        self._positive = positive_index

    def _probability(self, text: str) -> float:
        import torch  # noqa: PLC0415

        encoded = self._tokenizer(
            text[:MAX_CHARS],
            truncation=True,
            max_length=MAX_LENGTH,
            stride=STRIDE,
            return_overflowing_tokens=True,
            padding=True,
            return_tensors="pt",
        )
        inputs = {k: v for k, v in encoded.items() if k in {"input_ids", "attention_mask"}}
        with torch.inference_mode():
            logits = self._model(**inputs).logits
        probabilities = torch.softmax(logits, dim=-1)[:, self._positive]
        return float(probabilities.max())

    def score(self, texts: Sequence[str]) -> list[Verdict]:
        verdicts: list[Verdict] = []
        for text in texts:
            started = time.perf_counter()
            probability = min(1.0, max(0.0, self._probability(text)))
            verdicts.append(
                Verdict(
                    detector=self.id,
                    is_injection=probability >= self.threshold,
                    score=probability,
                    threshold=self.threshold,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            )
        return verdicts


def download(spec: ModelSpec, token: str | None) -> str:
    """Fetch the pinned snapshot into the Hub cache (explicit CLI action only)."""
    from huggingface_hub import snapshot_download  # noqa: PLC0415
    from huggingface_hub.errors import GatedRepoError, HfHubHTTPError  # noqa: PLC0415

    try:
        return str(
            snapshot_download(
                repo_id=spec.repo_id,
                revision=spec.revision,
                token=token,
                allow_patterns=["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer*"],
            )
        )
    except GatedRepoError:
        raise ModelUnavailableError(
            f"'{spec.repo_id}' is gated: accept its licence on huggingface.co with your account "
            "and set HF_TOKEN in .env, or use `models download protectai-deberta` as the "
            "documented stand-in"
        ) from None
    except HfHubHTTPError as exc:
        raise ModelUnavailableError(f"download failed ({type(exc).__name__})") from None
