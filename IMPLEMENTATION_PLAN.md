# Implementation Plan — Prompt-Injection Detector Benchmark

> Four prompt-injection detectors compared on catching attacks without blocking normal users — plus a published set of tricky benign prompts.

Project documentation: [PRD.md](PRD.md) · [TRD.md](TRD.md) · [APPFLOW.md](APPFLOW.md) · [UI_UX_DESIGN.md](UI_UX_DESIGN.md) · [BACKEND_SCHEMA.md](BACKEND_SCHEMA.md) · **IMPLEMENTATION_PLAN.md** · [WORKLOG.md](WORKLOG.md) · [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md) · [CLAUDE.md](CLAUDE.md) · [PROMPT_PLAYBOOK.md](PROMPT_PLAYBOOK.md)

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

## 1. How to use this plan

- Tasks are executed **in order**. Reordering requires the user's approval (PROMPT_PLAYBOOK §13).
- Each task has a ready-to-paste prompt in [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md).
- "d" = one focused day (~6–8 h). Total: **≈ 3.75 focused days** (stretch tasks excluded).
  At ~1–1.5 h on weekdays plus longer weekends, budget roughly 2 weekends plus a few weekday evenings (writing the hard-negative set is the slow part).
- A task is complete only when its acceptance criteria are verified and WORKLOG.md is updated.
- **Reuse:** M0.1 ports P01's provider layer and eval runner, and P02's Kaggle fine-tune notebook is the starting point for detector C.
- **Build local, benchmark hosted (TRD §S10):** every task up to M3.2 runs locally (B and C on CPU, D on Ollama) and needs no API key. M3.2 closes the build-complete checkpoint; MB.1 (hosted Groq D rows) starts after it and runs in the background while MF.1 proceeds.

## 2. Milestones and tasks

| Task | Title | Depends on | Effort |
|---|---|---|---|
| M0.1 | Port the lean foundation from P01 | — | 0.5 d |
| M1.1 | deepset download, language tags and splits | M0.1 | 0.25 d |
| M1.2 | Hard-negative set: schema, tooling and the first 150 prompts | M1.1 | 0.5 d |
| M1.3 | A (rules), B (Prompt Guard 2, local CPU) and the scoring harness | M1.2 | 0.5 d |
| M2.1 | C — fine-tuned classifier on Kaggle, Hub push, CPU inference | M1.3 | 0.5 d |
| M2.2 | D — LLM judge (local Ollama) | M1.3 | 0.25 d |
| M3.1 | Threshold sweep, per-language results and failure examples | M2.1, M2.2 | 0.5 d |
| M3.2 | Gradio Space and dataset publication | M3.1 | 0.5 d |
| MB.1 | Hosted benchmark: D judge on Groq (background) | M3.2 | 0.25 d (+ ~1 day of unattended budget pacing) |
| MF.1 | README, resume bullet and LinkedIn draft | M3.2 (hosted D rows from MB.1 added when they finish) | 0.25 d |


### M0 — Foundation (port from P01)

#### M0.1 · Port the lean foundation from P01

**Objective:** Start from P01's tested provider layer and eval runner instead of rebuilding them.

**Scope:**
- Copy from `../01-receipt-extractor`: `pyproject.toml` tool sections, `src/receipt_extractor/{llm,eval,ui/theme.py}`, `config.py`, `cli.py` skeleton, `configs/{models,pricing}.yaml`, the matching tests, `.gitignore`, `.gitattributes`, `.env.example`; rename the package to `injection_bench`.
- Trim `configs/models.yaml` to the aliases this project uses: local `ollama-qwen3-4b`; hosted `groq-oss-20b` (benchmark/Space only); keep `pricing.yaml` dated (Ollama = $0).
- Add the `profiles:` block and `LLM_PROFILE` setting (TRD §S10): roles `judge` (local `ollama-qwen3-4b`, hosted `groq-oss-20b`); `llm.resolve(role)` returns the alias for the active profile; unknown role or profile = clear error. `.env.example` sets `LLM_PROFILE=local`; Groq keys are left blank and optional.
- Confirm each Ollama tag with `ollama show <tag>` and time one typical request (prompt and output tokens/s); record both in WORKLOG (TRD §S10). Add the `hosted` pytest marker (skips without `GROQ_API_KEY`).
- Prompt Guard 2 is not an LLM-layer alias: it is a local `transformers` model registered next to C's (TRD §3).
- If P01's M0.4 (eval runner) is not finished yet, build §S3/§S4 from the TRD instead (≈ 1 d) and say so in WORKLOG.
- README skeleton: Results (header only), Quickstart, Architecture, Evaluation, Limitations.

**Done when:**
- Fresh clone + `uv sync` + `uv run pytest` succeeds on Windows PowerShell.
- `uv run injection_bench llm ping` (no flags → role `judge`, profile `local`) answers from Ollama with no API key set.


### M1 — Day 1 — hard negatives, rules, Prompt Guard, scorer

#### M1.1 · deepset download, language tags and splits

**Objective:** Fixed, reproducible attack/benign splits.

**Scope:**
- `cli data prepare` downloads `deepset/prompt-injections` (revision pinned), tags language (lightweight detector, e.g. `lingua`), carves validation (15 %, stratified, seed 42).
- `cli data stats`: label balance by language and split.

**Done when:**
- Split sizes (546/116 before carving) and licence confirmed in WORKLOG.

#### M1.2 · Hard-negative set: schema, tooling and the first 150 prompts

**Objective:** The slow, valuable part: a reusable benign-but-suspicious set, written before any detector sees it.

**Scope:**
- JSONL schema, `cli hn validate` (duplicates, lengths, categories), `cli hn coverage` (counts per category, target ≥ 15 each).
- Agent drafts candidate prompts per category into `data_own/hard_negatives.draft.jsonl`; the human edits, rejects and adds, then moves accepted rows into `hard_negatives.jsonl` with `author: udai`.
- Dataset card draft (`data_own/README.md`): purpose, categories, licence CC-BY-4.0, limitations.

**Done when:**
- ≥ 150 human-accepted prompts covering every category; coverage report committed.

#### M1.3 · A (rules), B (Prompt Guard 2) and the scoring harness

**Objective:** The two cheapest detectors and the metrics every detector is judged by.

**Scope:**
- Detector protocol; recall/FPR/precision/F1 with bootstrap CIs; per-language breakdown.
- A: rules in `configs/rules.yaml` (id, pattern, note), per-rule hit counts.
- B: `cli models download prompt-guard` fetches `meta-llama/Llama-Prompt-Guard-2-86M` at a pinned revision (needs the human's HF token after licence acceptance); CPU inference wrapper loaded once; 512-token chunking with max score; output mapped to a 0–1 score.
- Runs on validation, test and hard negatives.

**Done when:**
- Rows for A and B in `reports/results.csv` (test + hard negatives).


### M2 — Day 2 — fine-tuned classifier, LLM judge

#### M2.1 · C — fine-tuned classifier on Kaggle, Hub push, CPU inference

**Objective:** The trainable detector with a threshold you choose.

**Scope:**
- `notebooks/finetune_injection.ipynb` (adapt P02's notebook): DeBERTa-v3-small on train', scores for validation and test, model + card pushed by the human.
- `cli import-predictions`; CPU inference wrapper at a pinned Hub revision; scores on hard negatives computed locally.

**Done when:**
- Notebook ready; human action logged; after the run, C scores exist for validation, test and hard negatives.

#### M2.2 · D — LLM judge

**Objective:** The flexible but costly detector.

**Scope:**
- Versioned judge prompt; structured verdict; runs on validation, test and hard negatives on the local profile (`ollama-qwen3-4b`), one request at a time.
- Hosted (Groq) D rows are **not** part of this task; they run in MB.1 after the build-complete checkpoint.

**Done when:**
- Local D rows (`ollama-qwen3-4b`) in `reports/results.csv`, with measured CPU latency.


### M3 — Day 3 — threshold sweep, demo, publish

#### M3.1 · Threshold sweep, per-language results and failure examples

**Objective:** The trade-off picture and the operating point you'd ship.

**Scope:**
- Sweep C on validation; pick the operating point by a stated rule (e.g. max recall at FPR ≤ 2 % on validation benign); report it on test + hard negatives.
- Recall-vs-FPR chart with B and D as points; en/de table.
- Label ≥ 20 misses/false alarms; note attacks that got past every detector and why.

**Done when:**
- Charts + sweep CSV committed; failures labelled; README-ready summary in `reports/results.md`.

#### M3.2 · Gradio Space and dataset publication

**Objective:** Paste a prompt, see four verdicts; the hard-negative set public on the Hub.

**Scope:**
- Blocks app with four tabs; `app.py`; Space requirements; `DEMO_MODE` fallbacks.
- B and C run on the Space CPU; D uses role `judge`: `LLM_PROFILE=local` (Ollama) on the laptop, `LLM_PROFILE=hosted` (Groq) as a Space variable; documented in DEPLOY.md.
- This task closes the **build-complete checkpoint** (TRD §S10): the app works end to end on the local profile; record it in WORKLOG.
- Dataset card final; `docs/DEPLOY.md` with the Space and dataset push steps (human).

**Done when:**
- Local app works; DEPLOY.md complete; WORKLOG lists Space and dataset URLs once published.


### MB — Benchmark (hosted, after the build-complete checkpoint)

#### MB.1 · Hosted benchmark: D judge on Groq (background)

**Objective:** Add the hosted LLM-judge rows without ever blocking the build.

**Scope:**
- Hosted smoke run: the locked judge prompt version on 10 validation prompts with `groq-oss-20b`; a needed change becomes a new prompt version and the local D rows are re-run with it.
- D on validation, test and hard negatives with `groq-oss-20b` (run configs name the alias); ~130K tokens ≈ one Groq day; background.
- `cli report` rebuilds the tables and the recall-vs-FPR chart with local and hosted D points.

**Done when:**
- Hosted D rows with list cost per 1k; chart regenerated; WORKLOG records run ids and days used.


### MF — Ship — write-up and distribution

#### MF.1 · README, resume bullet and LinkedIn draft

**Objective:** Turn measurements into the artefact recruiters read.

**Scope:**
- README leads with recall / FPR / latency per detector and the threshold curve; a 'Scope and ethics' section; direct vs indirect injection explained.
- Fill resume-bullet brackets; `docs/LINKEDIN_DRAFT.md` on the false-positive finding; GIF script.

**Done when:**
- README renders with results above the fold; reproduce commands verified from a clean clone.
