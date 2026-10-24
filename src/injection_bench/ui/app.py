"""Gradio Blocks demo: Results, Try it, Hard negatives, About (FR-8, UI_UX_DESIGN).

No business logic here: callbacks call :mod:`injection_bench.ui.service`.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import gradio as gr

from injection_bench.ui import service

REPORTS = Path("reports")
HN_DIR = Path("data_own")
ABOUT = (
    "**Scope.** Defensive only. Attacks come from the public deepset dataset; the benign hard "
    "negatives are written for this project. Text you paste is classified in memory and never "
    "executed, forwarded to a tool-using model or logged. Direct injection is benchmarked; "
    "indirect (in-document) injection is not.\n\n"
    "**Reading the numbers.** The test split is small (116 prompts), so intervals are wide. A "
    "detector that blocks real users never ships: look at false positives on the hard negatives, "
    "not only recall."
)


def _results_table() -> list[list[str]]:
    path = REPORTS / "results.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if "[" not in r["variant"]]
    return [
        [
            r["detector"],
            r["variant"],
            r["subset"],
            r["n"],
            r["recall"],
            r["fpr"],
            r["latency_p50_ms"],
        ]
        for r in rows
    ]


def _hard_negatives() -> list[list[str]]:
    for name in ("hard_negatives.jsonl", "hard_negatives.draft.jsonl"):
        path = HN_DIR / name
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            return [[d["id"], d["category"], d["text"]] for d in map(json.loads, lines) if d]
    return []


def build(factories: dict[str, service.DetectorFactory], *, demo_mode: bool = False) -> Any:
    cache: dict[str, Any] = {}

    def try_it(text: str) -> tuple[list[list[str]], str]:
        try:
            rows, request_id = service.check(text, factories, cache)
        except service.InputError as exc:
            return [], str(exc)
        return service.as_table(rows), f"request {request_id}"

    with gr.Blocks(title="Prompt-injection detectors") as demo:
        gr.Markdown("# Prompt-injection detector benchmark\nFour detectors, one hard-negative set.")
        if demo_mode:
            gr.Markdown("**Demo mode:** live LLM-judge checks are limited per day.")
        with gr.Tab("Results"):
            gr.Dataframe(
                value=_results_table(),
                headers=["Detector", "Variant", "Subset", "n", "Recall", "FPR", "p50 ms"],
                interactive=False,
            )
        with gr.Tab("Try it"):
            box = gr.Textbox(label="Prompt to check", lines=5, max_length=service.MAX_CHARS)
            go = gr.Button("Check", variant="primary")
            table = gr.Dataframe(
                headers=["Detector", "Verdict", "Score", "Latency", "Evidence"], interactive=False
            )
            note = gr.Markdown()
            go.click(try_it, box, [table, note])
        with gr.Tab("Hard negatives"):
            gr.Dataframe(
                value=_hard_negatives(), headers=["id", "category", "text"], interactive=False
            )
        with gr.Tab("About"):
            gr.Markdown(ABOUT)
    demo.queue(default_concurrency_limit=2, max_size=20)
    return demo
