# Prompt-Injection Detector Benchmark

> Four prompt-injection detectors compared on catching attacks without blocking normal users, plus a
> published set of tricky benign prompts.

| Detector | What it is | Where it runs |
|---|---|---|
| **A** rules | 25 regex/keyword rules (English, German, Spanish), per-rule hit counts | CPU, < 1 ms |
| **B** Prompt Guard 2 | `meta-llama/Llama-Prompt-Guard-2-86M` (gated; ungated stand-in documented) | local CPU via `transformers` |
| **C** fine-tuned | DeBERTa-v3-small trained on deepset (Kaggle), threshold chosen on validation | local CPU |
| **D** LLM judge | structured verdict from a chat model behind the role `judge` | local Ollama (build) / Groq (benchmark, Space) |

## Results

_Results table: filled from `reports/results.md` once the benchmark runs are finished and the
hard-negative set is human-accepted (every number here comes from a run in `runs/`)._

## Quickstart (Windows PowerShell)

```powershell
uv sync --extra models                                  # base + torch/transformers for B and C
Copy-Item .env.example .env                              # build needs no API key (LLM_PROFILE=local)
uv run injection_bench data prepare                      # deepset download, language tags, splits
uv run injection_bench hn validate                       # hard-negative set checks
uv run injection_bench eval run -d A                     # rules on validation, test, hard negatives
uv run injection_bench eval run -d D                     # LLM judge on local Ollama (qwen3:4b-instruct)
uv run injection_bench report build                      # reports/results.csv + results.md
uv run pytest -q ; uv run ruff check . ; uv run mypy src # quality gates
```

Local LLM: `ollama pull qwen3:4b-instruct`. Detector B needs `uv run injection_bench models download
prompt-guard-2` after accepting the model licence on Hugging Face and setting `HF_TOKEN` (or
`protectai-deberta` as the ungated stand-in). Detector C is trained by `notebooks/finetune_injection.ipynb`
on Kaggle and imported with `uv run injection_bench import-predictions <folder>`.

## Architecture

```text
prompt -> A rules | B Prompt Guard 2 | C fine-tuned | D LLM judge (role "judge" -> profile -> alias)
deepset splits + hard negatives -> eval runner -> runs/<id>/{results.jsonl,summary.json,manifest.json}
                                                -> reports/{results.csv,results.md}
```

- All model calls go through the provider layer (`src/injection_bench/llm`): aliases and profiles in
  `configs/models.yaml`, disk cache, token-bucket limits, retries, dated list prices.
- All experiments go through the eval runner (`src/injection_bench/eval`): resumable, one JSON line per
  case, bootstrap confidence intervals, English and German reported separately.
- No database: results are files.

## Evaluation

- Data: `deepset/prompt-injections` at a pinned revision (Apache-2.0): 465 train / 81 validation (15 %
  stratified, seed 42) / 116 test. Test is small, so every metric carries a 95 % bootstrap interval.
- Hard negatives (`data_own/`): benign prompts that look suspicious, in 8 categories. Written and accepted
  by the author before any detector sees them; never used for training or tuning. Only FPR is computed on
  them.
- Thresholds: C is swept on validation only; B and D use their native decision.

## Scope and ethics

Defensive only. No attacks are generated: attacks come from the public deepset dataset. Pasted text in
the demo is classified, never executed or forwarded to a tool-using model, and never logged.
Direct injection (text typed into the prompt) is benchmarked; indirect injection (instructions hidden in
documents a model reads) is discussed but not benchmarked in v2.

## Limitations

See the results table notes; the numbers are specific to this dataset, these thresholds and this small
test split. Rule thresholds were tuned on validation, so validation numbers for A are optimistic.

Project documents: [PRD](PRD.md) · [TRD](TRD.md) · [WORKLOG](WORKLOG.md)
