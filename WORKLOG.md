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
| Current task | Waiting on human actions (hard negatives, Kaggle C, HF token) |
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

## 2026-10-24 — M1.2 · Hard-negative set: schema, tooling and the first 150 prompts

**Done:** `data/hard_negatives.py` (Pydantic schema, validator: schema/length/category/duplicate id and text with case/accent/punctuation-insensitive matching, author rule), coverage report, `to_cases`, `resolve_path` (human-accepted file wins, else the draft). CLI `hn validate` and `hn coverage --write`. Agent-drafted **160 candidates** (8 categories × 20) in `data_own/hard_negatives.draft.jsonl` (`author: claude-draft`); coverage report `reports/hn_coverage.md`; dataset card draft `data_own/README.md` (CC-BY-4.0).
- Verification: 10 new tests (schema errors with line numbers, duplicates, authors, coverage, CLI, committed draft is valid and covers every category); ruff + mypy clean.
**Files:** `src/injection_bench/data/hard_negatives.py`, `src/injection_bench/cli.py`, `tests/unit/data/test_hard_negatives.py`, `data_own/*`, `reports/hn_coverage.md`.
**Decisions:**
- The agent never writes `hard_negatives.jsonl`. Detector runs fall back to the draft when the final file is absent, and every run record carries `hn_status: draft|final`; **no README number may come from a draft-status run** (CLAUDE.md §5).
- Console output stays ASCII (Windows cp1252 consoles crash on `≥`).
**Open:**
- **Human action (the slow, valuable part):** read `data_own/hard_negatives.draft.jsonl`; reject, edit and add rows; move accepted rows into `data_own/hard_negatives.jsonl` with `author: udai`; run `uv run injection_bench hn validate` and `hn coverage`. M1.2 is not "done" until >= 150 human-accepted prompts exist. Until then all hard-negative FPR numbers are provisional.

## 2026-10-24 — M1.3 / M2.1 / M2.2 / M3.1 (code) · Detectors A, B, D, C pipeline, harness and sweep

**Done:** Detector protocol and `Verdict`; eval runner (resumable, `results.jsonl`/`summary.json`/`manifest.json`), metrics with 95 % bootstrap CIs and per-language blocks, report builder, `eval run`, `report build`, `report sweep`, `import-predictions`, `models download`.
- **A** rules v2 (25 rules, `configs/rules.yaml`); v2 added rules after reading *validation* misses only. **B** wrapper over `transformers` (512-token chunks, max score). **D** judge `judge-v1` on role `judge` (local `ollama-qwen3-4b`). **C**: Kaggle notebook `notebooks/finetune_injection.ipynb` (asserts split id hashes), importer, validation-only threshold sweep + chart code (tested on synthetic scores).
- Runs (all provisional on hard negatives = agent DRAFT set; test is n=116):

| Det | validation recall | test recall [CI] | HN-draft FPR | p50 latency |
|---|---|---|---|---|
| A rules-v2 | 0.73 (tuned on it) | 0.30 [0.19, 0.42] | 0.100 | < 1 ms |
| B protectai-deberta (stand-in) | 0.57 | 0.37 [0.25, 0.49] | 0.363 | ~165 ms |
| D qwen3:4b-instruct, judge-v1 | 0.63 | 0.32 [0.20, 0.44] | 0.056 | ~6.4 s |

  All FPR on benign deepset prompts = 0 for A/B/D. Validation-to-test drop for A shows validation overfit.
- Verification: 223 tests pass (2 opt-in skipped); ruff and mypy clean.
**Files:** `src/injection_bench/{detectors,eval}/*`, `configs/rules.yaml`, `notebooks/*`, `tests/unit/{detectors,eval}/*`, `reports/results.{csv,md}`, `README.md`.
**Decisions:**
- B ran on the **ungated stand-in** `protectai/deberta-v3-base-prompt-injection-v2` (Prompt Guard 2 is gated, no HF token): logged swap per TRD §3. Its high HN false-positive rate is a finding, not final.
- D latency was measured while other work ran on the CPU in the first ~third of the run; re-time idle before quoting it.
- `llm_calls.jsonl` is one file at `runs/` (not per run).
**Open:**
- Human action: accept the hard negatives; HF token + Prompt Guard 2 licence then `models download prompt-guard-2` and `eval run -d B`; run the Kaggle notebook, `import-predictions`, local `eval run -d C --c-path`, then `report sweep`.
- Not yet built: M3.2 Gradio app/DEPLOY.md, MB.1 hosted run (needs Groq key), MF.1 final README numbers.

## 2026-10-24 — M3.2 · Gradio app and deploy notes (local)

**Done:** `ui/service.py` (input cap 2,000 chars, per-detector failure isolation, no text logged or leaked in errors, detectors built once), `ui/app.py` (tabs: Results, Try it, Hard negatives, About; queue limits), `app.py` entry, `docs/DEPLOY.md`. Smoke: `python app.py` served HTTP 200 locally. 227 tests pass; ruff + mypy clean.
**Files:** `src/injection_bench/ui/*`, `app.py`, `docs/DEPLOY.md`, `tests/unit/ui/*`.
**Decisions:** Demo B currently uses the stand-in; switch to Prompt Guard 2 once downloaded. `DEMO_MODE` daily budget/cached fallback is NOT implemented yet (banner only).
**Open:** Build-complete checkpoint NOT reached: needs C (Kaggle), accepted hard negatives, Prompt Guard 2, DEMO_MODE budget, a manual UI check of "Try it" with Ollama running. Human action: publish steps in DEPLOY.md.

## 2026-10-24 — M3.x follow-ups · timing, demo budget, failures, second local judge

**Done:**
- `eval run --no-cache` and an idle-machine D timing run (30 uncached test cases, `qwen3:4b-instruct`): **p50 4.5 s, p95 6.6 s** (the earlier 6.4 s p50 was measured partly under load; that run's cached rows stay as they are, the timing run is labelled "(timing, no cache)").
- `ui/budget.py`: per-UTC-day cap on live judge checks (`DEMO_DAILY_REQUESTS`) used when `DEMO_MODE=true`; fails closed on unreadable state; tests added. Limit row replaces the judge row when spent (no cached-showcase fallback yet).
- `injection_bench failures` -> `reports/failures.csv` (241 rows, draft heuristic labels) and `reports/failure_notes.md`; 33 cases missed by every detector.
- Browser check of "Try it" in the pane: attack prompt -> A, B, D flag it, C "unavailable" (not trained), no stack traces; B row relabelled "classifier (stand-in)".
- Second local judge row, `llama3.2:3b`, judge-v1: validation recall 0.53, test recall 0.18, hard-negative (draft) FPR 0.013, p50 ~3.5 s (run while idle). Smaller model = fewer false alarms, fewer catches.
- Drafts: `docs/MODEL_CARD_DRAFT.md`, `docs/LINKEDIN_DRAFT.md` (numbers bracketed).
- Verification: tests, ruff, mypy pass.
**Files:** `src/injection_bench/{ui/budget.py,eval/failures.py,cli.py,detectors/factory.py,ui/*}`, `reports/*`, `docs/*`, `tests/unit/{ui,eval}/*`.
**Decisions:** llama3.2 numbers are provisional on the draft hard-negative set like all FPR figures.
**Open:** unchanged human actions (accept hard negatives; HF token + Prompt Guard 2; Kaggle C; publish). README results table still not filled: waits for accepted hard negatives.

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
