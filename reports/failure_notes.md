# Failure notes (draft, 2026-10-24)

Source: `reports/failures.csv` (`injection_bench failures`), 241 rows across A, B, D on validation,
test and the **draft** hard negatives. Labels are heuristic first guesses; the human confirms them in
the CSV (columns `failure_label`, `note`, `fixed_by`). Nothing here is tuned on test or the hard negatives.

## Misses (all three detectors)
| Cause (draft label) | A | B | D | Reading |
|---|---:|---:|---:|---|
| non-English attack (de/other) | 19 | 17 | 19 | A's German rules help only for the shapes they list; B (English-trained stand-in) and the 4B judge miss German attacks too |
| attack inside long text | 7 | 5 | 7 | the instruction sits after benign filler; chunking helps B only partly |
| no known trigger phrase | 24 | 29 | 31 | persuasion or task-hijack without a classic phrase ("write a reason why X is the best", role questions) |

33 distinct cases are missed by every detector that scored them: the candidates for the README's
"attacks that got past everything" list. Many deepset "attacks" are task-hijacks that look like
ordinary requests, which also explains the low test recall of all three.

## False alarms (draft hard negatives; provisional)
- A (16): translation_imperative 8, quoted_errors 3, benign_roleplay 2: rules fire on quoted or
  translated attack phrases. A fix (quote/translation awareness) is a new rules version, evaluated on
  validation only, never tuned on this set.
- B stand-in (58): support_escalation 17, translation_imperative 14, quoted_errors 12, media 8: the
  classifier keys on imperative tone and "ignore/override" vocabulary, not on intent.
- D (9): support_escalation 5, media 3, quoted_errors 1: the judge is the most conservative on this set.

## Next
Human: confirm labels, accept or reject hard negatives (the FPR numbers move with the set), then
`fixed_by` entries after any rules v3 / threshold change. Target >= 20 labelled rows: already met
by volume; quality depends on your review.
