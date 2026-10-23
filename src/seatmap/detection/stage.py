"""Stage 2 - detection and tracking of desks, chairs and screens across frames.

Reads: 01_frames/. Writes to 02_detections/: per frame class (desk, chair, screen), mask,
confidence and track ID; debug/ (detections drawn on frames).
Technology: Ultralytics YOLO26-seg + BoT-SORT / ByteTrack.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'detection' is not implemented yet")
