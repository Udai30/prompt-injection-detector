---
license: apache-2.0
base_model: microsoft/deberta-v3-small
datasets: [deepset/prompt-injections]
tags: [prompt-injection, text-classification, guardrails]
---

# injection-detector-deberta-small (draft; fill `[...]` only from runs)

A DeBERTa-v3-small classifier fine-tuned to flag prompt-injection text. Part of the
Prompt-Injection Detector Benchmark (detector **C**). Defensive use only.

## Training
- Data: `deepset/prompt-injections` at revision `4f61ecb0…` (Apache-2.0), train' = 465 prompts
  (English and German); 81 held out for validation (15 %, stratified, seed 42); 116 test.
- Setup: see `notebooks/finetune_injection.ipynb` ([epochs], [lr], [batch], [GPU], [seed 42]).
- The hard-negative set was **not** used for training or tuning.

## Operating point
Threshold [x.xx], chosen on validation only: max recall with validation FPR <= 2 %.

## Results (95 % bootstrap CI; small test split)
| Subset | Recall | FPR |
|---|---|---|
| deepset test (en / de separately) | [..] | [..] |
| Hard negatives (n=[N]) | n/a | [..] |

## Limitations
Tiny training set; mostly short prompts; English/German only; direct injection only (no
in-document injection); not a security boundary; a detector is one layer of defence.
