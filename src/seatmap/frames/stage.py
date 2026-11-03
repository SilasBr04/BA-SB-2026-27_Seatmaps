"""Stage 1 - frame extraction: sharp frames and a keyframe subset from the room video.

Reads: the run's video. Writes to 01_frames/: frames/*.jpg, frames.json (frame number,
timestamp, sharpness, keyframe flag, video metadata), debug/ (keyframe contact sheet,
sharpness-over-time plot). Technology: OpenCV.

Steps (docs/technical-setup.md, section 5.4):

1. Read the video metadata. OpenCV applies the rotation metadata of smartphone videos while
   decoding, so stored frames are upright; the rotation angle is only recorded.
2. Sample frames at `sample_fps`, decoding sequentially (seeking is unreliable for phone videos).
3. Resize to `target_width` (downscaling only) and write every sampled frame to disk.
4. Sharpness = variance of the Laplacian of the resized grayscale frame. Frames below
   `min_sharpness_ratio` x the mean sharpness are dropped and their files deleted.
5. Keyframes: the sampled time span is split into equal windows, one per keyframe; normally the
   sharpest kept frame of each window becomes a keyframe. Windows without kept frames stay empty.
   Number of windows: `num_keyframes`, but at most one per `min_keyframe_interval_s`, so short
   videos get fewer keyframes (cutoff at num_keyframes x interval, e.g. 40 x 1.5 s = 60 s).
   Adjacent keyframes must be at least `min_keyframe_gap_s` apart: the sharpest frame of two
   neighbouring windows can otherwise sit right at their shared border and show the same view.
   With this gap, the selection is optimized over the whole video: as many windows as possible
   get a keyframe, then total sharpness is maximized (a slightly less sharp frame may be taken
   so the next window is not blocked). A window that cannot get a keyframe stays empty.
"""

from __future__ import annotations

import json
from bisect import bisect_right
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from cv2.typing import MatLike

from seatmap.errors import UserError
from seatmap.frames import debug
from seatmap.images import write_image
from seatmap.runs import Run

FRAMES_DIRNAME = "frames"
FRAMES_JSON = "frames.json"
JPEG_QUALITY = 95
CONTACT_SHEET = "keyframes.jpg"
SHARPNESS_PLOT = "sharpness.png"
DEBUG_FILES = (CONTACT_SHEET, SHARPNESS_PLOT)


@dataclass(frozen=True)
class Settings:
    sample_fps: float
    target_width: int
    num_keyframes: int
    min_sharpness_ratio: float
    min_keyframe_interval_s: float
    min_keyframe_gap_s: float

    @classmethod
    def from_config(cls, config: Any) -> Settings:
        if not isinstance(config, dict):
            raise UserError("frames: the 'frames' section of the run config is missing")
        missing = [name for name in cls.__dataclass_fields__ if name not in config]
        if missing:
            # e.g. a run created before the key existed; its frozen config.yaml must be updated
            raise UserError(f"frames: missing settings in the run config: {', '.join(missing)}")
        settings = cls(
            sample_fps=number(config, "sample_fps"),
            target_width=whole_number(config, "target_width"),
            num_keyframes=whole_number(config, "num_keyframes"),
            min_sharpness_ratio=number(config, "min_sharpness_ratio"),
            min_keyframe_interval_s=number(config, "min_keyframe_interval_s"),
            min_keyframe_gap_s=number(config, "min_keyframe_gap_s"),
        )
        if settings.sample_fps <= 0 or settings.target_width <= 0 or settings.num_keyframes <= 0:
            raise UserError("frames: sample_fps, target_width and num_keyframes must be > 0")
        if settings.min_keyframe_interval_s <= 0:
            raise UserError("frames: min_keyframe_interval_s must be > 0")
        # windows are at least min_keyframe_interval_s wide, so a smaller gap always leaves room
        if not 0 <= settings.min_keyframe_gap_s < settings.min_keyframe_interval_s:
            raise UserError(
                "frames: min_keyframe_gap_s must be >= 0 and below min_keyframe_interval_s"
            )
        if not 0 <= settings.min_sharpness_ratio <= 1:  # <= 1 keeps at least the sharpest frame
            raise UserError("frames: min_sharpness_ratio must be between 0 and 1")
        return settings


def number(config: dict[str, Any], name: str) -> float:
    value = config[name]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UserError(f"frames: {name} must be a number, got {value!r}")
    return float(value)


def whole_number(config: dict[str, Any], name: str) -> int:
    """An integer setting; 40.0 is accepted, 40.9 is rejected instead of truncated."""
    value = number(config, name)
    if not value.is_integer():
        raise UserError(f"frames: {name} must be a whole number, got {config[name]!r}")
    return int(value)


@dataclass(frozen=True)
class VideoInfo:
    path: str
    fps: float
    frame_count: int  # from the container metadata; may be inaccurate
    duration_s: float  # timestamp of the last decoded frame
    width: int  # size of the decoded (upright) frames, before resizing
    height: int
    rotation: int  # rotation metadata in degrees, already applied by OpenCV


@dataclass
class Frame:
    index: int  # frame number in the source video
    timestamp_s: float
    sharpness: float
    kept: bool = False
    keyframe: bool = False
    file: str | None = None  # relative to 01_frames/, None for dropped frames


def execute(run: Run) -> None:
    settings = Settings.from_config(run.config.get("frames"))
    out_dir = run.stage_dir("frames")
    frames_dir = out_dir / FRAMES_DIRNAME
    frames_dir.mkdir(exist_ok=True)
    debug_dir = run.debug_dir("frames")
    # stage may be re-run; remove the previous outputs first so a failed re-run leaves no
    # manifest or debug figures behind that belong to other settings
    (out_dir / FRAMES_JSON).unlink(missing_ok=True)
    for name in DEBUG_FILES:
        (debug_dir / name).unlink(missing_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()

    video, frames = sample_frames(run.video, settings, frames_dir)
    mean, threshold = drop_blurry(frames, settings.min_sharpness_ratio, out_dir)
    span = frames[-1].timestamp_s - frames[0].timestamp_s
    windows = select_keyframes(frames, keyframe_count(span, settings), settings.min_keyframe_gap_s)

    kept = [f for f in frames if f.kept]
    keyframes = [f for f in frames if f.keyframe]
    summary = {
        "sampled": len(frames),
        "kept": len(kept),
        "dropped": len(frames) - len(kept),
        "keyframes": len(keyframes),
        "keyframe_windows": len(windows),
        "empty_keyframe_windows": sum(1 for w in windows if w is None),
        "mean_sharpness": mean,
        "sharpness_threshold": threshold,
    }
    data = {
        "video": asdict(video),
        "settings": asdict(settings),
        "summary": summary,
        "frames": [asdict(f) for f in frames],
    }
    (out_dir / FRAMES_JSON).write_text(json.dumps(data, indent=2), encoding="utf-8")

    debug.write_contact_sheet(keyframes, out_dir, debug_dir / CONTACT_SHEET)
    debug.write_sharpness_plot(frames, threshold, windows, debug_dir / SHARPNESS_PLOT)

    print(
        f"frames: {summary['sampled']} sampled, {summary['kept']} kept, "
        f"{summary['keyframes']} keyframes ({summary['empty_keyframe_windows']} empty windows)"
    )


def sample_frames(
    path: Path, settings: Settings, frames_dir: Path
) -> tuple[VideoInfo, list[Frame]]:
    """Decode the video, keep one frame per 1/sample_fps seconds, resize and write it."""
    if not path.is_file():
        raise UserError(f"video not found: {path}")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise UserError(f"cannot open video: {path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            raise UserError(f"video has no valid frame rate: {path}")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        rotation = int(cap.get(cv2.CAP_PROP_ORIENTATION_META))

        step = 1.0 / settings.sample_fps
        next_t = 0.0
        frames: list[Frame] = []
        size: tuple[int, int] | None = None
        timestamp = 0.0
        index = -1
        while cap.grab():
            index += 1
            timestamp = frame_timestamp(cap, index, fps)
            if timestamp + 1e-6 < next_t:
                continue
            ok, image = cap.retrieve()
            if not ok:  # corrupt frame: keep the slot open for the next decodable one
                continue
            while next_t <= timestamp + 1e-6:
                next_t += step
            if size is None:
                size = (image.shape[1], image.shape[0])
            image = resize_to_width(image, settings.target_width)
            name = f"frame_{index:06d}.jpg"
            write_image(frames_dir / name, image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            file = f"{FRAMES_DIRNAME}/{name}"
            frames.append(Frame(index, round(timestamp, 3), sharpness(image), file=file))
    finally:
        cap.release()

    if not frames or size is None:
        raise UserError(f"no frames could be decoded from {path}")
    video = VideoInfo(
        path=str(path),
        fps=fps,
        frame_count=frame_count,
        duration_s=round(timestamp, 3),
        width=size[0],
        height=size[1],
        rotation=rotation,
    )
    return video, frames


def frame_timestamp(cap: cv2.VideoCapture, index: int, fps: float) -> float:
    """Presentation time of the last grabbed frame; handles variable frame rate videos."""
    msec = cap.get(cv2.CAP_PROP_POS_MSEC)
    if msec > 0 or index == 0:
        return float(msec) / 1000.0
    return index / fps


def resize_to_width(image: MatLike, target_width: int) -> MatLike:
    height, width = image.shape[:2]
    if width <= target_width:
        return image
    target_height = round(height * target_width / width)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def sharpness(image: MatLike) -> float:
    """Variance of the Laplacian: high for crisp edges, low for motion blur."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)


def drop_blurry(frames: list[Frame], ratio: float, out_dir: Path) -> tuple[float, float]:
    """Mark frames below `ratio` x mean sharpness as dropped, delete their files.

    Returns the mean sharpness and the threshold, unrounded: the reported threshold is exactly
    the value the frames were compared with.
    """
    mean = float(np.mean([f.sharpness for f in frames]))
    threshold = ratio * mean
    for frame in frames:
        frame.kept = frame.sharpness >= threshold
        if not frame.kept and frame.file is not None:
            (out_dir / frame.file).unlink(missing_ok=True)
            frame.file = None
    return mean, threshold


def keyframe_count(span_s: float, settings: Settings) -> int:
    """`num_keyframes`, reduced for short videos to one keyframe per `min_keyframe_interval_s`."""
    by_length = floor_ratio(span_s, settings.min_keyframe_interval_s)
    return max(1, min(settings.num_keyframes, by_length))


def select_keyframes(
    frames: list[Frame], num_keyframes: int, min_gap_s: float = 0.0
) -> list[Frame | None]:
    """Split the sampled time span into equal windows and flag at most one kept frame per
    window, with adjacent keyframes at least `min_gap_s` apart.

    The choice is optimal over the whole video, not greedy per window: first as many windows
    as possible get a keyframe, then the total sharpness is maximized. Without gap conflicts
    this is the sharpest kept frame of each window. A greedy choice could take a frame at the
    right edge of a window and so block every candidate of the next one.

    Returns one entry per window (None for windows without a suitable kept frame).
    """
    for frame in frames:  # flags of an earlier selection must not survive
        frame.keyframe = False
    start, end = frames[0].timestamp_s, frames[-1].timestamp_s
    width = (end - start) / num_keyframes
    windows: list[list[Frame]] = [[] for _ in range(num_keyframes)]
    for frame in frames:
        if not frame.kept:
            continue
        slot = floor_ratio(frame.timestamp_s - start, width) if width > 0 else 0
        windows[min(slot, num_keyframes - 1)].append(frame)

    # Longest path over the kept frames in time order. score[i] = (keyframes, total
    # sharpness) of the best selection ending with frame i; best_upto[i] = index of the
    # best score among frames 0..i, so each predecessor lookup is a binary search.
    ordered = [f for window in windows for f in sorted(window, key=lambda f: f.timestamp_s)]
    times = [f.timestamp_s for f in ordered]
    score: list[tuple[int, float]] = []
    previous: list[int | None] = []
    best_upto: list[int] = []
    first = 0  # index of the first frame of the current window in `ordered`
    for window in windows:
        for i in range(first, first + len(window)):
            # predecessors: frames of earlier windows that are at least min_gap_s earlier
            last = min(bisect_right(times, times[i] - min_gap_s + 1e-6), first) - 1
            pred = best_upto[last] if last >= 0 else None
            count, total = score[pred] if pred is not None else (0, 0.0)
            score.append((count + 1, total + ordered[i].sharpness))
            previous.append(pred)
        for i in range(first, first + len(window)):
            better = not best_upto or score[i] > score[best_upto[-1]]
            best_upto.append(i if better else best_upto[-1])
        first += len(window)

    node = best_upto[-1] if best_upto else None
    while node is not None:
        ordered[node].keyframe = True
        node = previous[node]
    return [next((f for f in window if f.keyframe), None) for window in windows]


def floor_ratio(a: float, b: float) -> int:
    """floor(a / b), robust to float error at exact multiples (0.6 / 0.2 = 2.999...)."""
    return int(round(a / b, 6))
