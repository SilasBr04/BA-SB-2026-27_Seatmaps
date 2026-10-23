"""Comparison of a run's stage 6 layout with a reference map.

Metrics: seat count error, precision, recall, F1, preserved spatial relations.
"""

from __future__ import annotations

from pathlib import Path

from seatmap.runs import Run


def execute(run: Run, reference: Path) -> None:
    raise NotImplementedError("evaluation is not implemented yet")
