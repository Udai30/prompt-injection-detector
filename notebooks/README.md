# Notebooks (run by the human)

The build machine has no CUDA GPU (CLAUDE.md §4), so GPU work lives here as Kaggle notebooks.

| Notebook | Produces | Then |
|---|---|---|
| `finetune_injection.ipynb` | `outputs/predictions.jsonl` (validation + test scores), `outputs/model/` | `uv run injection_bench import-predictions <folder>`; hard negatives are scored locally with `eval run -d C --c-path <folder>/model` |

Regenerate nothing by hand: the notebook asserts the same split ids as `data prepare`.
