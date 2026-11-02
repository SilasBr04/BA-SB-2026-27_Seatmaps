"""Image file I/O shared by all stages.

cv2.imread/cv2.imwrite cannot handle non-ASCII paths on Windows and imwrite only reports
failure through its return value, so images are encoded in memory and written with pathlib.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np
from cv2.typing import MatLike


def write_image(path: Path, image: MatLike, params: Sequence[int] = ()) -> None:
    """Encode `image` in the format given by the file extension and write it; raise on failure."""
    ok, buffer = cv2.imencode(path.suffix, image, list(params))
    if not ok:
        raise ValueError(f"cannot encode image: {path}")
    path.write_bytes(buffer.tobytes())


def read_image(path: Path) -> MatLike | None:
    """Read a color image; None if the file is missing or cannot be decoded."""
    if not path.is_file():
        return None
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    image: MatLike | None = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return image
