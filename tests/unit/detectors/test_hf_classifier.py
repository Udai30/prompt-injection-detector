"""B/C wrapper: chunking, max over chunks, threshold, missing weights (no real weights)."""

from __future__ import annotations

from typing import Any

import pytest

torch = pytest.importorskip("torch")

from injection_bench.detectors import hf_classifier as hf  # noqa: E402


class FakeTokenizer:
    """Returns one chunk per 4 words, as `return_overflowing_tokens` would."""

    def __call__(self, text: str, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["truncation"] and kwargs["return_overflowing_tokens"]
        assert kwargs["max_length"] == hf.MAX_LENGTH
        words = text.split() or [""]
        chunks = [words[i : i + 4] for i in range(0, len(words), 4)]
        ids = torch.tensor([[len(w) for w in chunk] + [0] * (4 - len(chunk)) for chunk in chunks])
        return {
            "input_ids": ids,
            "attention_mask": (ids > 0).long(),
            "overflow_to_sample_mapping": 0,
        }


class FakeModel:
    """Chunks containing the token length 6 ('ignore') look like injections."""

    def __call__(self, input_ids: Any, attention_mask: Any) -> Any:
        del attention_mask
        hot = (input_ids == 6).any(dim=1).float()
        logits = torch.stack([(1 - hot) * 4, hot * 4], dim=1)

        class Out:
            pass

        out = Out()
        out.logits = logits  # type: ignore[attr-defined]
        return out

    def eval(self) -> None:  # pragma: no cover - interface parity
        return None


def detector(threshold: float = 0.5) -> hf.HFClassifierDetector:
    return hf.HFClassifierDetector(
        "B", "B: fake", FakeTokenizer(), FakeModel(), threshold=threshold
    )


def test_probability_is_the_max_over_chunks() -> None:
    long_benign_then_hot = "aa bb cc dd ee ff gg hh ignore ii jj kk"
    verdict = detector().score([long_benign_then_hot])[0]
    assert verdict.is_injection and verdict.score > 0.9
    assert verdict.detector == "B" and verdict.latency_ms >= 0


def test_benign_text_scores_low_and_threshold_moves_the_decision() -> None:
    assert not detector().score(["hello there pal"])[0].is_injection
    strict = detector(threshold=0.0).score(["hello there pal"])[0]
    assert strict.is_injection and strict.threshold == 0.0


def test_pinned_revisions_are_full_commit_hashes() -> None:
    for spec in hf.MODELS.values():
        assert len(spec.revision) == 40 and int(spec.revision, 16) >= 0
    assert hf.MODELS["prompt-guard-2"].gated and not hf.MODELS["protectai-deberta"].gated


def test_missing_local_weights_give_an_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    with pytest.raises(hf.ModelUnavailableError, match="models download"):
        hf.load_backend(hf.MODELS["protectai-deberta"], source=str(tmp_path / "nope"))
