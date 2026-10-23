"""Stage 4 - 2D top view: each furniture item exactly once as a footprint, plus floor points.

Reads: 02_detections/ and 03_reconstruction/. Writes to 04_topview/: 2D footprints per
furniture item, floor points of the room; debug/ (top-view plot).
Technology: Open3D, NumPy, shapely, scikit-learn.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'topview' is not implemented yet")
