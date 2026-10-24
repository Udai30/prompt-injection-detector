"""Build a detector by id from settings (the single place that knows how each one is wired)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from injection_bench.core.types import Detector, DetectorId
from injection_bench.detectors.hf_classifier import (
    MODELS,
    HFClassifierDetector,
    ModelUnavailableError,
    load_backend,
)
from injection_bench.detectors.rules import RuleDetector

if TYPE_CHECKING:
    from injection_bench.config import Settings
    from injection_bench.llm.providers import Provider


def build_detector(
    detector_id: DetectorId,
    settings: Settings,
    *,
    model: str | None = None,
    threshold: float | None = None,
    c_path: Path | None = None,
    provider: Provider | None = None,
    rules_path: Path | None = None,
    run_dir: Path | None = None,
    use_cache: bool = True,
) -> tuple[Detector, str]:
    """Return ``(detector, variant label)``.

    ``model`` is an LLM alias (D) or a key of ``MODELS`` (B).
    """
    if detector_id == "A":
        detector_a = RuleDetector.from_path(rules_path or Path("configs/rules.yaml"))
        return detector_a, f"rules-v{detector_a.version}"
    if detector_id == "B":
        spec = MODELS[model or "prompt-guard-2"]
        tokenizer, backend = load_backend(spec)
        return (
            HFClassifierDetector(
                "B",
                f"B: {spec.key}",
                tokenizer,
                backend,
                positive_index=spec.positive_index,
                threshold=0.5 if threshold is None else threshold,
            ),
            spec.key,
        )
    if detector_id == "C":
        if c_path is None:
            raise ModelUnavailableError(
                "C needs the fine-tuned model directory: pass --c-path (see notebooks/README.md)"
            )
        spec = MODELS["protectai-deberta"]  # only for the label order; weights come from c_path
        tokenizer, backend = load_backend(spec, source=str(c_path))
        return (
            HFClassifierDetector(
                "C",
                "C: fine-tuned DeBERTa",
                tokenizer,
                backend,
                positive_index=1,
                threshold=0.5 if threshold is None else threshold,
            ),
            f"deberta-small@{c_path.name}",
        )
    from injection_bench.detectors.judge import PROMPT_VERSION, LLMJudge  # noqa: PLC0415
    from injection_bench.llm import JSONLSink, build_client  # noqa: PLC0415

    sinks = [JSONLSink(run_dir / "llm_calls.jsonl")] if run_dir else []
    client = build_client(settings, cache=use_cache, sinks=sinks, provider=provider)
    alias = model or client.registry.resolve("judge", settings.llm_profile)
    return LLMJudge(client, alias), f"{alias}/{PROMPT_VERSION}"
