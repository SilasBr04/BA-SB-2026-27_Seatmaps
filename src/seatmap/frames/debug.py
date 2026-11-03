"""Debug visualizations of stage 1: keyframe contact sheet and sharpness-over-time plot."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from seatmap.images import read_image, write_image

if TYPE_CHECKING:
    from seatmap.frames.stage import Frame

THUMB_WIDTH = 320
SHEET_COLUMNS = 8
LABEL_HEIGHT = 22

PLOT_SIZE = (1400, 500)  # width, height in px
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 80, 20, 40, 50

# BGR colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
GREEN = (60, 160, 60)
RED = (60, 60, 220)
BLUE = (200, 110, 30)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def write_contact_sheet(keyframes: Sequence[Frame], frames_root: Path, path: Path) -> None:
    """Grid of keyframe thumbnails, each labelled with frame number and timestamp."""
    thumbs = []
    for frame in keyframes:
        if frame.file is None:
            continue
        image = read_image(frames_root / frame.file)
        if image is None:
            print(f"Warning: keyframe image missing or unreadable, skipped: {frame.file}")
            continue
        height = round(image.shape[0] * THUMB_WIDTH / image.shape[1])
        thumb = cv2.resize(image, (THUMB_WIDTH, height), interpolation=cv2.INTER_AREA)
        label = np.full((LABEL_HEIGHT, THUMB_WIDTH, 3), 255, dtype=np.uint8)
        text = f"#{frame.index}  {frame.timestamp_s:.1f}s  sharp {frame.sharpness:.0f}"
        cv2.putText(label, text, (4, 16), FONT, 0.45, BLACK, 1, cv2.LINE_AA)
        thumbs.append(np.vstack([label, thumb]))
    if not thumbs:
        path.unlink(missing_ok=True)  # do not leave a sheet from an earlier run behind
        return

    cell_h = max(t.shape[0] for t in thumbs)
    columns = min(SHEET_COLUMNS, len(thumbs))
    rows = -(-len(thumbs) // columns)
    sheet = np.full((rows * cell_h, columns * THUMB_WIDTH, 3), 255, dtype=np.uint8)
    for i, thumb in enumerate(thumbs):
        y, x = (i // columns) * cell_h, (i % columns) * THUMB_WIDTH
        sheet[y : y + thumb.shape[0], x : x + THUMB_WIDTH] = thumb
    write_image(path, sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])


def write_sharpness_plot(
    frames: Sequence[Frame],
    threshold: float,
    windows: Sequence[Frame | None],
    path: Path,
) -> None:
    """Sharpness per sampled frame over time: kept (green), dropped (red), keyframes (blue
    rings), the drop threshold (dashed) and the keyframe window boundaries (gray)."""
    width, height = PLOT_SIZE
    plot = np.full((height, width, 3), 255, dtype=np.uint8)
    x0, x1 = MARGIN_LEFT, width - MARGIN_RIGHT
    y0, y1 = height - MARGIN_BOTTOM, MARGIN_TOP

    t_start, t_end = frames[0].timestamp_s, frames[-1].timestamp_s
    t_span = max(t_end - t_start, 1e-6)
    s_max = max(max(f.sharpness for f in frames), threshold) * 1.05 or 1.0

    def px(t: float, s: float) -> tuple[int, int]:
        return (
            round(x0 + (t - t_start) / t_span * (x1 - x0)),
            round(y0 - s / s_max * (y0 - y1)),
        )

    for i in range(len(windows) + 1):
        x = round(x0 + i / len(windows) * (x1 - x0))
        cv2.line(plot, (x, y1), (x, y0), GRAY, 1)

    cv2.line(plot, (x0, y0), (x1, y0), BLACK, 1)
    cv2.line(plot, (x0, y0), (x0, y1), BLACK, 1)
    for i in range(6):
        s = s_max * i / 5
        _, y = px(t_start, s)
        cv2.line(plot, (x0 - 5, y), (x0, y), BLACK, 1)
        cv2.putText(plot, f"{s:.0f}", (8, y + 4), FONT, 0.4, BLACK, 1, cv2.LINE_AA)
    for i in range(11):
        t = t_start + t_span * i / 10
        x, _ = px(t, 0)
        cv2.line(plot, (x, y0), (x, y0 + 5), BLACK, 1)
        cv2.putText(plot, f"{t:.0f}s", (x - 12, y0 + 22), FONT, 0.4, BLACK, 1, cv2.LINE_AA)

    _, ty = px(t_start, threshold)
    for x in range(x0, x1, 12):
        cv2.line(plot, (x, ty), (min(x + 6, x1), ty), RED, 1)

    points = [px(f.timestamp_s, f.sharpness) for f in frames]
    cv2.polylines(plot, [np.array(points, dtype=np.int32)], False, GRAY, 1, cv2.LINE_AA)
    for frame, point in zip(frames, points, strict=True):
        cv2.circle(plot, point, 3, GREEN if frame.kept else RED, -1, cv2.LINE_AA)
        if frame.keyframe:
            cv2.circle(plot, point, 7, BLUE, 2, cv2.LINE_AA)

    kept = sum(f.kept for f in frames)
    keyframes = sum(f.keyframe for f in frames)
    title = (
        f"Sharpness (Laplacian variance) - {len(frames)} sampled, {kept} kept, "
        f"{keyframes}/{len(windows)} keyframes, threshold {threshold:.0f} (dashed)"
    )
    cv2.putText(plot, title, (x0, 25), FONT, 0.55, BLACK, 1, cv2.LINE_AA)
    cv2.putText(plot, "time", (x1 - 40, height - 8), FONT, 0.45, BLACK, 1, cv2.LINE_AA)
    write_image(path, plot)
