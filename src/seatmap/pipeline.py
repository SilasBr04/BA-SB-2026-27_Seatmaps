"""Ordered registry of the pipeline stages (see docs/technical-setup.md, section 5.2)."""

from __future__ import annotations

from collections.abc import Callable

from seatmap.detection import stage as detection
from seatmap.export import stage as export
from seatmap.frames import stage as frames
from seatmap.layout import stage as layout
from seatmap.reconstruction import stage as reconstruction
from seatmap.runs import Run
from seatmap.seats import stage as seats
from seatmap.topview import stage as topview

STAGES: dict[str, Callable[[Run], None]] = {
    "frames": frames.execute,
    "detection": detection.execute,
    "reconstruction": reconstruction.execute,
    "topview": topview.execute,
    "seats": seats.execute,
    "layout": layout.execute,
    "export": export.execute,
}


def run_all(run: Run, start: str | None = None) -> None:
    """Run all stages in order, optionally starting at `start`."""
    names = list(STAGES)
    for name in names[names.index(start) if start else 0 :]:
        STAGES[name](run)
