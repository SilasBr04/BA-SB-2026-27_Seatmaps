"""Stage 7 - export of BeSeated entity records plus an SVG preview.

Reads: 06_layout/. Writes to 07_export/: room_<room>.json (name, shape, type, x, y, width,
height per element) and room_<room>.svg (preview). Technology: Pydantic, svgwrite.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'export' is not implemented yet")
