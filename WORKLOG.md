# Worklog — Prompt-Injection Detector Benchmark

> Four prompt-injection detectors compared on catching attacks without blocking normal users — plus a published set of tricky benign prompts.

Project documentation: [PRD.md](PRD.md) · [TRD.md](TRD.md) · [APPFLOW.md](APPFLOW.md) · [UI_UX_DESIGN.md](UI_UX_DESIGN.md) · [BACKEND_SCHEMA.md](BACKEND_SCHEMA.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · **WORKLOG.md** · [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md) · [CLAUDE.md](CLAUDE.md) · [PROMPT_PLAYBOOK.md](PROMPT_PLAYBOOK.md)

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

Format: **newest first**, one entry per task session (see CLAUDE.md §7).

```text
## YYYY-MM-DD — Task ID · Short title

**Done:** what was actually completed (incl. tests run + results, verification evidence)
**Files:** paths touched
**Decisions:** anything decided, and why
**Open:** anything unresolved — incl. "Human action:" items (Kaggle runs, publishing, accounts, secrets)
```

## Current state

| Item | Value |
|---|---|
| Current task | M1.2 — in progress |
| Last verified gate run | — |
| Pending human actions | see the entries below |

---

## 2026-10-24 — M0.1 · Port the lean foundation from P01

**Done:** Git set up (human request): own repo, remote `Udai30/prompt-injection-detector`, branches `main` (default), `dev`, `test`; initial commit pushed on all three, all later work committed/pushed on `test` only. Ported P01's `llm/` provider layer and `config.py` (package renamed `injection_bench`), added `profiles:` + `ModelRegistry.resolve(role, profile)` and `LLM_PROFILE` (default `local`), trimmed `configs/models.yaml` to `ollama-qwen3-4b` / `ollama-llama3-2-3b` / `ollama-qwen3-8b` (stretch) / `groq-oss-20b` plus the registered local `prompt-guard-2` and offline `deberta-small`; `pricing.yaml` dated (Ollama = $0). CLI skeleton with `llm ping` (no flags = role `judge`, profile `local`). `live` / `hosted` / `models` opt-in pytest markers. README skeleton.
- Verification: `uv run pytest -q` 154 passed, 2 skipped (opt-in); `-m live` ping passed against real Ollama (qwen3:4b-instruct, first call 20 s incl. model load, no API key set); ruff check + format and `mypy src` clean.
- Local model tags present on the machine: `qwen3:4b-instruct`, `llama3.2:3b`, `qwen3:8b`. A typical-request timing (tokens/s) is recorded in M2.2 with the real judge prompt.
**Files:** `pyproject.toml`, `.env.example`, `.gitignore`, `.gitattributes`, `configs/{models,pricing}.yaml`, `src/injection_bench/{__init__,config,cli}.py`, `src/injection_bench/llm/*`, `tests/**`.
**Decisions:**
- P01's eval runner is receipt-specific (scorer, tasks, report); only the LLM layer and settings were ported. The detector eval runner is written fresh for this task set (TRD §S4) in M1.3.
- Gemini support stays in the ported provider layer but no Gemini alias is configured (not in this project's matrix).
- `torch` / `transformers` are an optional extra (`uv sync --extra models`) so the base install stays light; B and C need them.
- CLAUDE.md §1 updated: the human now allows commit + push on `test` only (same rule as P07).
**Open:** Human action: `ollama pull` tags already present; HF token + Prompt Guard 2 licence before M1.3's B runs.

## 2026-10-24 — M1.1 · deepset download, language tags and splits

**Done:** `data prepare` downloads `deepset/prompt-injections` at pinned revision `4f61ecb0…` (licence **apache-2.0** confirmed from the dataset card), tags language with `lingua` (en / de / other), carves validation (15 %, stratified by label, seed 42) from the original train split and writes `data/deepset/{train,validation,test}.jsonl` + `splits.json` (ids, ids_hash, language tags). `data stats` prints label balance by language and split. Domain contracts (`Case`, `Verdict`, `Detector` protocol) added in `core/types.py`.
- Split sizes: 546 original train → **465 train' + 81 validation**; **116 test** (matches the spec). Test: en 29 benign / 37 injection, de 27 / 21, other 0 / 2. Validation: en 23/15, de 28/12, other 0/3. `other` (French etc.) is reported on its own line, never merged into en/de.
- Verification: 6 new unit tests (stratified + seeded carve, disjoint splits, stable ids_hash, stats, errors, lingua en/de) offline; real download run once; ruff + mypy clean.
**Files:** `src/injection_bench/{core/types.py,data/deepset.py,cli.py,config.py}`, `tests/unit/data/test_deepset.py`, `.env.example`.
**Decisions:** Language tags come from lingua restricted to six Latin-script languages; anything not en/de is `other`. The test split is small (116): every later number carries a bootstrap CI.
**Open:** Human action (optional): set `HF_TOKEN` in `.env` for faster downloads.

## 2026-10-23 — DOCS · Build local, benchmark hosted (v2.1)

**Done:** Re-architected the LLM access for the build (human request, 2026-10-23: "build the app first
on local, then use APIs for benchmarks; don't wait for free-tier resets"). Documents updated: TRD (§3,
§S1, §S3, §S6, §S9, new §S10), CLAUDE.md §4, PRD, IMPLEMENTATION_PLAN, IMPLEMENTATION_PROMPTS and,
where affected, APPFLOW and UI_UX_DESIGN. No code exists yet.
**Files:** the `*.md` files above.
**Decisions:**
- Three phases (TRD §S10): **build** on local Ollama (`LLM_PROFILE=local`, no API key needed), **benchmark** on Groq after the build-complete checkpoint (background, paced), **demo** on Groq in the Space (`LLM_PROFILE=hosted`).
- Code asks for an LLM role; `configs/models.yaml` gains a `profiles:` block mapping roles to aliases.
- Build: M0.1–M3.2 run locally: B (Prompt Guard 2 86M) now runs on CPU via `transformers` instead of Groq; D (role `judge`) runs on Ollama `qwen3:4b-instruct`.
- Benchmark: MB.1 (new): D judge on validation, test and hard negatives with `groq-oss-20b`, ~1 Groq day in the background after M3.2.
- Machine: i5 12th gen, 16 GB RAM, Iris Xe treated as CPU-only; ≤ 4B at Q4 by default, 8B only as an overnight stretch. M0.1 measures tokens/s and sweeps are planned from it.
**Open:**
- Human action: Ollama for Windows is installed (0.32.6, used by P01); before M0.1 run `ollama pull qwen3:4b-instruct`; on Hugging Face, accept the licence for `meta-llama/Llama-Prompt-Guard-2-86M` and put a read token in `.env` as `HF_TOKEN` (before M1.3).
- Human action: Groq API key → `.env` only when the benchmark task starts (and as a Space secret); not needed for any build task.

## 2026-10-22 — DOCS · Project documentation created (v2, lean)

**Done:** Created PRD, TRD, APPFLOW, UI_UX_DESIGN, BACKEND_SCHEMA, IMPLEMENTATION_PLAN,
IMPLEMENTATION_PROMPTS, CLAUDE.md and the project copy of PROMPT_PLAYBOOK.md from the ideas doc
"Portfolio Projects: 3 Quick Wins + 3 Flagships" (2026-10-22). No code exists yet.
**Files:** all `*.md` in the project root.
**Decisions:**
- v2 follows the ideas doc: a detector benchmark (A rules, B Prompt Guard 2, C fine-tuned, D LLM judge) with a published hard-negative set. v1's agent/tool-use guardrail angle is out of scope.
- Hard negatives are written before any detector runs on them, to avoid tuning the set to a detector.
- Defensive scope only: public attacks, own benign prompts, own setup.
**Open:**
- Human action: finish P01's M0.R and M0.4 first (M0.1 here ports them).
- Human action: superseded by the 2026-10-23 entry (Prompt Guard 2 runs locally; Groq key only before MB.1).
- Human action: Hugging Face write token (model + dataset push) and Kaggle phone verification before M2.1.
- Human action: block 2–3 hours for writing/editing the hard negatives in M1.2 — this is your work, not the agent's.
