"""Latency instrumentation.

Records real, measured wall-clock time per pipeline stage -- never invented.
Stages that run concurrently (see pipeline.py) will overlap in wall-clock
time, so the sum of stage times can exceed total_ms; that's expected and is
why total_ms is measured separately around the whole request rather than
summed from the stages.
"""

from __future__ import annotations

import time
from contextlib import contextmanager


class Timer:
    def __init__(self):
        self.stages: dict[str, float] = {}

    @contextmanager
    def measure(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            # accumulate in case a stage name is measured more than once
            # (e.g. per-claim work aggregated under one label)
            self.stages[name] = self.stages.get(name, 0.0) + elapsed_ms

    def as_dict(self, round_to: int = 1) -> dict:
        return {k: round(v, round_to) for k, v in self.stages.items()}
