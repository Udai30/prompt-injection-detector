# Working Agreements for Claude Code — Prompt-Injection Detector Benchmark

> Four prompt-injection detectors compared on catching attacks without blocking normal users — plus a published set of tricky benign prompts.

Project documentation: [PRD.md](PRD.md) · [TRD.md](TRD.md) · [APPFLOW.md](APPFLOW.md) · [UI_UX_DESIGN.md](UI_UX_DESIGN.md) · [BACKEND_SCHEMA.md](BACKEND_SCHEMA.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [WORKLOG.md](WORKLOG.md) · [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md) · **CLAUDE.md** · [PROMPT_PLAYBOOK.md](PROMPT_PLAYBOOK.md)

| Field | Value |
|---|---|
| Project | P03 · `03-prompt-injection-detectors` |
| Type | Quick win 3 of 3 |
| Skill it adds | AI security, guardrails |
| Target role signal | AI/GenAI Engineer · LLM security · guardrails · evaluation rigour |
| Effort | ≈ 3.75 focused days (sum of task estimates; the ideas doc says 2–3 days) |
| Public artefact | Hugging Face Space + fine-tuned model + hard-negative dataset on the HF Hub |
| Interface | Gradio 5 → Hugging Face Space |
| Status | Specification v2.1 (lean, local-first build) · 2026-10-23 |

---

These rules override the generic playbook wherever they are stricter.

## 1. Git is read-only

Allowed: `git status`, `log`, `diff`, `show`, `blame`. Forbidden: `init`, `add`, `commit`, `push`,
`pull`, `branch`, `checkout -b`, `merge`, `rebase`, `reset`, `tag`, `stash`, any `config` change,
and staging files "ready to commit". Do not offer to commit at the end of a task. The human handles git.

## 2. No database

v2 has no database. Results are files (TRD §S4). Do not add Postgres, SQLite-as-app-state, Docker
Compose or an ORM without a PRD change approved by the human. (Read-only SQLite *datasets* used by an
experiment are data, not app state.)

## 3. Environments

- Python: `uv` only (`uv sync`, `uv run …`, `uv add …`). No global `pip install`. No Node toolchain.
- If a global install is genuinely unavoidable, say so explicitly and state how to remove it.
- Datasets and model weights are downloaded only by explicit CLI commands into `data/` or the model
  cache — never at import time or app startup.

## 4. Free tier and external services

- **Build local, benchmark hosted (TRD §S10).** Every build task runs on local Ollama models
  with `LLM_PROFILE=local`; no build task may need an API key or wait for a free-tier reset. Hosted
  (Groq) calls happen only in benchmark tasks after the build-complete checkpoint, and in the Space.
  If a build task seems to need a hosted model, stop and ask instead of adding the dependency.
- Only the providers in `configs/models.yaml` (local Ollama/llama.cpp, Groq free plan, Gemini API
  free tier) and free hosting (Hugging Face Hub + Spaces). Never add a paid API, even "just for a
  baseline".
- Code asks for an LLM *role*; the profile resolves it to an alias. Never hard-code a model string.
- Use the disk cache and fixed subsets. Hosted benchmark sweeps respect daily budgets: plan them
  across days, run them in the background and record that in WORKLOG.md. Long local sweeps run one
  request at a time (overnight if needed) and their timing is recorded.
- Gemini's free tier may use submitted data — send it public dataset content only, never user input.
- The machine has no CUDA GPU. GPU work is written as a Kaggle notebook under `notebooks/` for the
  human to run; its outputs come back through `cli import-predictions`.
- Publishing (HF Hub pushes, Space creation, PyPI uploads) is a **human action**: prepare it, list
  the exact commands in WORKLOG, and stop.

## 5. Project invariants

- Defensive scope only: no new attack generation; attacks come from the public deepset dataset. Pasted demo text is classified, never executed or forwarded to a tool-using model, and never logged.
- The hard-negative set is written (by the human, with agent-drafted candidates the human edits) before any detector is run on it, and is never used for training or tuning.
- C's threshold is chosen on the validation split only; test and hard negatives are touched only for final runs.
- English and German are always reported separately.
- All model calls go through the provider layer (TRD §S3); all experiments go through the eval runner
  (TRD §S4). A number that is not produced by a run does not go in the README.

## 6. Commands

```powershell
uv sync                                   # install
uv run ruff check . ; uv run mypy src ; uv run pytest -q
uv run injection_bench --help                  # CLI
uv run python app.py                      # local Gradio demo
```

## 7. WORKLOG format

Newest first: `## YYYY-MM-DD — Task ID · Short title`, then **Done / Files / Decisions / Open**.
Tests, verification, security and performance notes go under Done/Open — they must be recorded.
A task is not finished until its entry exists.

## 8. Documentation stays true

When a decision changes, update its owning document (PRD/TRD/APPFLOW/UI_UX_DESIGN/BACKEND_SCHEMA)
in the same task and log the change in WORKLOG.md.
