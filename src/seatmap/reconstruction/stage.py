"""Stage 3 - camera motion and depth from the keyframes.

Reads: keyframes from 01_frames/. Writes to 03_reconstruction/: camera poses, depth maps
(.npy), point cloud (.ply); debug/. Technology: VGGT (fallback: COLMAP).
Independent of stage 2.
"""

from __future__ import annotations

from seatmap.runs import Run


def execute(run: Run) -> None:
    raise NotImplementedError("stage 'reconstruction' is not implemented yet")
