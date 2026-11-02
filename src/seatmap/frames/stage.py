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
5. Keyframes: the sampled time span is split into equal windows, one per keyframe; the sharpest
   kept frame of each window becomes a keyframe. Windows without kept frames stay empty.
   Number of windows: `num_keyframes`, but at most one per `min_keyframe_interval_s`, so short
   videos get fewer keyframes (cutoff at num_keyframes x interval, e.g. 40 x 1.5 s = 60 s).
   Adjacent keyframes must be at least `min_keyframe_gap_s` apart: the sharpest frame of two
   neighbouring windows can otherwise sit right at their shared border and show the same view.
   A window whose kept frames are all too close to the previous keyframe stays empty.
"""

from __future__ import annotations

import json
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


@dataclass(frozen=True)
class Settings:
    sample_fps: float
    target_width: int
    num_keyframes: int
    min_sharpness_ratio: float
    min_keyframe_interval_s: float
    min_keyframe_gap_s: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> Settings:
        missing = [name for name in cls.__dataclass_fields__ if name not in config]
        if missing:
            # e.g. a run created before the key existed; its frozen config.yaml must be updated
            raise UserError(f"frames: missing settings in the run config: {', '.join(missing)}")
        settings = cls(
            sample_fps=float(config["sample_fps"]),
            target_width=int(config["target_width"]),
            num_keyframes=int(config["num_keyframes"]),
            min_sharpness_ratio=float(config["min_sharpness_ratio"]),
            min_keyframe_interval_s=float(config["min_keyframe_interval_s"]),
            min_keyframe_gap_s=float(config["min_keyframe_gap_s"]),
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
    settings = Settings.from_config(run.config["frames"])
    out_dir = run.stage_dir("frames")
    frames_dir = out_dir / FRAMES_DIRNAME
    frames_dir.mkdir(exist_ok=True)
    # stage may be re-run; remove the manifest first so a failed re-run leaves none behind
    (out_dir / FRAMES_JSON).unlink(missing_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()

    video, frames = sample_frames(run.video, settings, frames_dir)
    threshold = drop_blurry(frames, settings.min_sharpness_ratio, out_dir)
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
        "mean_sharpness": float(np.mean([f.sharpness for f in frames])),
        "sharpness_threshold": threshold,
    }
    data = {
        "video": asdict(video),
        "settings": asdict(settings),
        "summary": summary,
        "frames": [asdict(f) for f in frames],
    }
    (out_dir / FRAMES_JSON).write_text(json.dumps(data, indent=2), encoding="utf-8")

    debug_dir = run.debug_dir("frames")
    debug.write_contact_sheet(keyframes, out_dir, debug_dir / "keyframes.jpg")
    debug.write_sharpness_plot(frames, threshold, windows, debug_dir / "sharpness.png")

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


def drop_blurry(frames: list[Frame], ratio: float, out_dir: Path) -> float:
    """Mark frames below `ratio` x mean sharpness as dropped, delete their files; return the
    threshold."""
    threshold = ratio * float(np.mean([f.sharpness for f in frames]))
    for frame in frames:
        frame.kept = frame.sharpness >= threshold
        if not frame.kept and frame.file is not None:
            (out_dir / frame.file).unlink(missing_ok=True)
            frame.file = None
    return round(threshold, 2)


def keyframe_count(span_s: float, settings: Settings) -> int:
    """`num_keyframes`, reduced for short videos to one keyframe per `min_keyframe_interval_s`."""
    by_length = floor_ratio(span_s, settings.min_keyframe_interval_s)
    return max(1, min(settings.num_keyframes, by_length))


def select_keyframes(
    frames: list[Frame], num_keyframes: int, min_gap_s: float = 0.0
) -> list[Frame | None]:
    """Split the sampled time span into equal windows and flag the sharpest kept frame of each
    that is at least `min_gap_s` after the previous keyframe.

    Returns one entry per window (None for windows without a suitable kept frame).
    """
    start, end = frames[0].timestamp_s, frames[-1].timestamp_s
    width = (end - start) / num_keyframes
    windows: list[list[Frame]] = [[] for _ in range(num_keyframes)]
    for frame in frames:
        if not frame.kept:
            continue
        slot = floor_ratio(frame.timestamp_s - start, width) if width > 0 else 0
        windows[min(slot, num_keyframes - 1)].append(frame)

    chosen: list[Frame | None] = []
    previous: Frame | None = None
    for window in windows:
        candidates = [
            f
            for f in window
            if previous is None or f.timestamp_s - previous.timestamp_s >= min_gap_s - 1e-6
        ]
        best = max(candidates, key=lambda f: f.sharpness, default=None)
        if best is not None:
            best.keyframe = True
            previous = best
        chosen.append(best)
    return chosen


def floor_ratio(a: float, b: float) -> int:
    """floor(a / b), robust to float error at exact multiples (0.6 / 0.2 = 2.999...)."""
    return int(round(a / b, 6))
