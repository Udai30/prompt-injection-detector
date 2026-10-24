---
license: cc-by-4.0
language: [en]
task_categories: [text-classification]
pretty_name: Prompt-Injection Hard Negatives
tags: [prompt-injection, guardrails, false-positives, benign]
---

# Prompt-Injection Hard Negatives (draft card)

Benign prompts that *look* like prompt injections. Prompt-injection detectors are usually scored on
how many attacks they catch; this set measures the other axis: how often they block ordinary users.

**Status:** `hard_negatives.draft.jsonl` holds agent-drafted candidates. The published set is
`hard_negatives.jsonl`, written and accepted by the author (`author: udai`) *before* any detector
was run on it. It is never used for training or tuning.

## Categories (fixed list)

meta_questions, media_instructions, quoted_errors, code_role_keys, security_education,
benign_roleplay, translation_imperative, support_escalation (>= 15 prompts each).

## Fields

`id` (`hn-0001`…), `text` (<= 1,000 chars, English), `category`, `why_tricky`, `author`, `created`.
Every row is benign: the only metric computed on it is the false-positive rate.

## Licence and limitations

CC-BY-4.0. English only; a few prompts quote short foreign-language strings (translation category).
Sized for a false-positive estimate with wide confidence intervals, not for training. Defensive use
only: it contains no attacks.
