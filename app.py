"""Hugging Face Space / local entry point: ``uv run python app.py``."""

from __future__ import annotations

import os
from pathlib import Path

from injection_bench.config import get_settings
from injection_bench.ui import app as ui
from injection_bench.ui import service
from injection_bench.ui.budget import DailyBudget

if __name__ == "__main__":
    settings = get_settings()
    c_dir = os.environ.get("C_MODEL_PATH")
    demo = ui.build(
        service.default_factories(settings, Path(c_dir) if c_dir else None),
        demo_mode=settings.demo_mode,
        live_gate=DailyBudget(
            settings.llm_cache_dir.parent / "demo_budget.json", settings.demo_daily_requests
        ).try_acquire,
    )
    demo.launch()
