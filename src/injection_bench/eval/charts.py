"""Recall-vs-FPR chart: C's threshold curve with A, B and D as single points (M3.1).

FPR here is the false-positive rate on benign prompts of the chosen subset; the curve comes from the
validation/test sweep, the points from finished runs. Matplotlib is used headless (Agg).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from injection_bench.eval.sweep import SweepPoint

COLORS = {"A": "#7a7a7a", "B": "#1f77b4", "C": "#d62728", "D": "#2ca02c"}


def recall_vs_fpr(
    curve: Sequence[SweepPoint],
    operating: SweepPoint | None,
    points: Sequence[dict[str, Any]],
    path: Path,
    *,
    title: str = "Recall vs false-positive rate (deepset test)",
) -> None:
    """Write the chart. ``points`` are summary dicts of finished runs on the test split."""
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=140)
    xs = [p.fpr for p in curve if p.fpr is not None and p.recall is not None]
    ys = [p.recall for p in curve if p.fpr is not None and p.recall is not None]
    ax.plot(xs, ys, color=COLORS["C"], linewidth=1.8, label="C (threshold sweep)")
    if operating is not None and operating.fpr is not None and operating.recall is not None:
        ax.scatter(
            [operating.fpr],
            [operating.recall],
            color=COLORS["C"],
            marker="*",
            s=140,
            zorder=5,
            label=f"C @ {operating.threshold:.2f} (chosen on validation)",
        )
    for summary in points:
        m = summary["metrics"]
        if m["recall"]["value"] is None or m["fpr"]["value"] is None:
            continue
        ax.scatter(
            [m["fpr"]["value"]],
            [m["recall"]["value"]],
            color=COLORS.get(summary["detector"], "black"),
            marker="o",
            s=60,
            zorder=4,
            label=f"{summary['detector']}: {summary['variant']}",
        )
    ax.set_xlabel("False-positive rate (benign prompts)")
    ax.set_ylabel("Recall (injection prompts)")
    ax.set_xlim(-0.01, 1.01)
    ax.set_ylim(-0.01, 1.01)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
