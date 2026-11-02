"""Ordered registry of the pipeline stages (see docs/technical-setup.md, section 5.2)."""

from __future__ import annotations

from collections.abc import Callable

from seatmap.detection import stage as detection
from seatmap.errors import UserError
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


def stage_names(start: str | None = None, stop: str | None = None) -> list[str]:
    """Stage names in pipeline order from `start` to `stop` (both inclusive)."""
    names = list(STAGES)
    first = names.index(start) if start else 0
    last = names.index(stop) if stop else len(names) - 1
    if last < first:
        raise UserError(f"stage '{stop}' comes before stage '{start}'")
    return names[first : last + 1]
