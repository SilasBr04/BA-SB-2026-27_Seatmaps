"""Stage 1 - frame extraction: sharp frames and a keyframe subset from the room video.

Reads: the run's video. Writes to 01_frames/: frames/*.jpg, frames.json (frame number,
timestamp, sharpness, keyframe flag, video metadata), debug/ (keyframe contact sheet,
sharpness-over-time plot). Technology: OpenCV.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'frames' is not implemented yet")
