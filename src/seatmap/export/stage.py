"""Stage 7 - SVG export in BeSeated format.

Reads: 06_layout/. Writes to 07_export/: room_<room>.svg. Technology: svgwrite.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'export' is not implemented yet")
