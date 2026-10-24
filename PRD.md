# Product Requirements Document — Prompt-Injection Detector Benchmark

> Four prompt-injection detectors compared on catching attacks without blocking normal users — plus a published set of tricky benign prompts.

Project documentation: **PRD.md** · [TRD.md](TRD.md) · [APPFLOW.md](APPFLOW.md) · [UI_UX_DESIGN.md](UI_UX_DESIGN.md) · [BACKEND_SCHEMA.md](BACKEND_SCHEMA.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [WORKLOG.md](WORKLOG.md) · [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md) · [CLAUDE.md](CLAUDE.md) · [PROMPT_PLAYBOOK.md](PROMPT_PLAYBOOK.md)

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

## 1. Problem

Every company shipping LLM features worries about prompt injection, and few people can say how well a
filter actually works. Detection rate alone is misleading: a filter that blocks 10 % of real users
never ships. This project measures four detectors on both axes — catching attacks (recall) and leaving
normal users alone (false-positive rate on benign prompts that *look* suspicious) — and publishes the
hard-negative set so others can reuse it.

## 2. Users

| User | Need |
|---|---|
| Recruiter / hiring manager | AI-security depth that almost no 1-year candidate shows |
| Engineer adding guardrails | Which detector, at which threshold, at what false-positive cost |
| Demo visitor | Paste a prompt, see four verdicts with scores and latency |

## 3. Goals and non-goals

**Goals**
- G1. Four detectors (A rules, B Llama Prompt Guard 2, C fine-tuned classifier, D LLM judge) on identical ids.
- G2. A hand-written, published hard-negative set of 150–200 benign-but-suspicious prompts.
- G3. A threshold sweep for C with the operating point you would ship.
- G4. Model + dataset on the HF Hub; Space live.

**Non-goals**
- Generating new attacks, red-teaming third-party systems, jailbreak research. **Defensive only:**
  public datasets and your own benign prompts, measured on your own setup.
- Indirect (in-document) injection is discussed in the README but not benchmarked in v2.

## 4. Data

| Dataset | Source | Licence | Use |
|---|---|---|---|
| deepset/prompt-injections | Hugging Face — 662 labelled prompts (546 train / 116 test), some German | Apache-2.0 | Train C; test split = attack/benign benchmark; report English and German separately |
| Hard negatives (own) | Written by Udai for this project: 150–200 benign prompts that look suspicious ("ignore the background noise in this recording", "what does 'system prompt' mean?", support tickets quoting error messages) | Own work, published (CC-BY-4.0) | False-positive rate; the reusable artefact |

Facts carried from the ideas doc (2026-10-22); M1.1 re-verifies them. The 116-prompt test split is small:
report CIs and say so.

## 5. Success metrics

| Metric | Definition |
|---|---|
| Recall (primary) | share of injection prompts flagged, deepset test split |
| False-positive rate (primary) | share of hard negatives flagged |
| Precision / F1 | deepset test split, overall and per language |
| Latency p50/p95, cost / 1k checks | per detector |
| Operating point | C's threshold chosen on validation; recall at that FPR on test |

## 6. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | `cli data prepare`: deepset download, language tag (en/de), validation carved from train (stratified, seed 42). |
| FR-2 | Hard-negative set in `data_own/hard_negatives.jsonl` with category, author, notes; validator + category coverage report. |
| FR-3 | A: regex/keyword rules ("ignore previous", "you are now", base64 blobs, role-play markers) with per-rule hit logging. |
| FR-4 | B: Llama Prompt Guard 2 (86M) run locally on CPU with `transformers` (revision pinned); score + label. No API. |
| FR-5 | C: DeBERTa-v3-small (or DistilBERT) fine-tuned on deepset train on Kaggle; pushed to the Hub; CPU inference. |
| FR-6 | D: LLM judge behind the role `judge`: local Ollama `qwen3:4b-instruct` during the build, Groq `gpt-oss-20b` for the benchmark rows and the Space (TRD §S10); short classification prompt; structured verdict. |
| FR-7 | Threshold sweep for C (recall vs FPR curve), per-language results, failure examples per detector. |
| FR-8 | Gradio Space: Results, Try it (paste → four verdicts), Hard negatives (browse the set), About (scope + ethics). |

## 7. Acceptance criteria (project level)

- README leads with recall / FPR / latency per detector and the C threshold curve.
- Model and hard-negative dataset on the HF Hub with cards; Space live.
- ≥ 20 labelled misses/false alarms across detectors.

**Resume bullet:** Benchmarked 4 prompt-injection detectors (rules, Llama Prompt Guard 2, fine-tuned
DeBERTa, LLM judge) and published a [N]-prompt hard-negative set; the fine-tuned model reached [X]
recall at a [Y]% false-positive rate on benign prompts.

**Interview questions to prepare**
- Why can't a better system prompt solve injection?
- What's the difference between direct and indirect (in-document) injection, and which did you test?
- How did you pick the threshold, and what does a false positive cost the business?
- Which attacks got past every detector, and why?

---

## S1. Portfolio done bar (applies to every project in this portfolio)

Cut scope before cutting any of these. The project is done when it clears all six:

| # | Criterion | Concrete check for this repo |
|---|---|---|
| 1 | A measured result on a fixed test set | The eval split (ids + manifest hash) is committed or reproducibly downloadable; no metric is reported without it. Never "looks good". |
| 2 | A baseline you beat — and an honest note where you didn't | The results table contains at least one simple baseline; the README says where it wins |
| 3 | Latency and cost measured | p50/p95 latency and list-price cost per 1k requests, **even when the run was free** |
| 4 | A short failure list | 20–30 errors grouped by cause, with what each fix bought (before/after) |
| 5 | It runs somewhere a stranger can click | The public artefact in the header table exists and its link is in the README |
| 6 | A README that opens with the results table | First screen = a number a hiring manager can react to; then architecture, limitations, "what I'd do differently", reproduce steps |

Resume bullets carry `[brackets]` until filled — **only with numbers you measured**.

## S2. Constraints shared by the portfolio

- **Zero paid services.** Local models (Ollama / llama.cpp on CPU, 1–4B at Q4; 8B as an
  overnight stretch), Groq free plan, Gemini API free tier, Kaggle free GPUs (T4/P100, ~30 h/week),
  Hugging Face Hub + Spaces (free CPU). Nothing that needs a payment card to run the core experiments.
- **Build local, benchmark hosted.** The app is built and validated entirely on local Ollama models,
  so no build step waits on a free-tier quota. Hosted APIs (Groq) are used only for benchmark runs
  after the app works end to end, and for the public demo (TRD §S10).
- **Free-tier limits decide hosted sample sizes.** Hosted LLM runs use fixed 200–300-item subsets
  (Groq is roughly 1K requests and ~200K tokens per model per day) and run in the background;
  local and non-LLM methods run on the full test set where CPU time allows and are *also* scored on
  the same subset for a fair comparison. The README says so.
- **Public data only**, licences respected (no redistribution where prohibited — ship download
  scripts instead). Gemini's free tier may use submitted data: send it public dataset content only.
- **No employer code, prompts or data** in any repository.
- **Developer machine:** Windows, Intel i5 12th gen, 16 GB RAM, no CUDA GPU. Anything GPU-bound
  runs on Kaggle as a notebook the human runs.
- **Lean stack (v2):** no database, no Docker requirement, no web framework unless the product
  needs one. Results live in files (`runs/`, `reports/`) under git.

## S3. Out of scope for every project (v2)

- User accounts, authentication, multi-tenancy, billing.
- Storing user-submitted content (uploads and pasted text are processed in memory only).
- Databases, Docker Compose stacks, mobile apps.
- Paid observability, vector-DB or hosting products.
