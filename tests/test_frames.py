import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest
from cv2.typing import MatLike

from seatmap.errors import UserError
from seatmap.frames import stage
from seatmap.frames.stage import Frame, Settings, floor_ratio, keyframe_count, select_keyframes
from seatmap.runs import Run, create_run

FPS = 30
SECONDS = 10
SIZE = (640, 360)  # width, height


def blurred(second: float) -> bool:
    """Every frame within 0.2 s after a full second is blurred in the synthetic video."""
    return second % 1.0 < 0.2


def make_video(path: Path) -> None:
    rng = np.random.default_rng(0)
    texture = rng.integers(0, 256, size=(SIZE[1], SIZE[0] * 2, 3), dtype=np.uint8)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter.fourcc(*"mp4v"), FPS, SIZE)
    assert writer.isOpened()
    for i in range(FPS * SECONDS):
        offset = i * 2
        image: MatLike = np.ascontiguousarray(texture[:, offset : offset + SIZE[0]])
        if blurred(i / FPS):
            image = cv2.GaussianBlur(image, (31, 31), 10)
        writer.write(image)
    writer.release()


def make_run(tmp_path: Path, **frames: float) -> Run:
    video = tmp_path / "room.mp4"
    make_video(video)
    settings: dict[str, float] = {"sample_fps": 5, "target_width": 320, "num_keyframes": 8}
    settings |= {"min_sharpness_ratio": 0.5, "min_keyframe_interval_s": 1.0, **frames}
    return create_run(
        "4.02", video, {"frames": settings}, runs_root=tmp_path / "runs", now=datetime(2026, 11, 2)
    )


def test_stage_writes_sharp_frames_keyframes_and_debug(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    stage.execute(run)

    out = run.stage_dir("frames")
    data = json.loads((out / "frames.json").read_text(encoding="utf-8"))
    frames = data["frames"]

    assert data["video"]["fps"] == pytest.approx(FPS)
    assert (data["video"]["width"], data["video"]["height"]) == SIZE
    assert len(frames) == pytest.approx(5 * SECONDS, abs=1)
    assert frames[1]["timestamp_s"] - frames[0]["timestamp_s"] == pytest.approx(0.2, abs=0.04)

    for frame in frames:
        assert frame["kept"] == (not blurred(frame["timestamp_s"]))
        assert (frame["file"] is not None) == frame["kept"]
        assert not frame["keyframe"] or frame["kept"]

    files = sorted((out / "frames").glob("*.jpg"))
    assert len(files) == data["summary"]["kept"]
    image = cv2.imread(str(files[0]))
    assert image is not None
    assert image.shape[:2] == (180, 320)

    assert data["summary"]["keyframes"] == 8
    assert data["summary"]["keyframe_windows"] == 8
    assert (out / "debug" / "keyframes.jpg").is_file()
    assert (out / "debug" / "sharpness.png").is_file()


def test_rerun_replaces_previous_frames(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    stage.execute(run)
    stale = run.stage_dir("frames") / "frames" / "frame_999999.jpg"
    stale.write_bytes(b"")

    stage.execute(run)
    assert not stale.exists()


def test_small_videos_are_not_upscaled(tmp_path: Path) -> None:
    run = make_run(tmp_path, target_width=1280)
    stage.execute(run)
    image = cv2.imread(str(next((run.stage_dir("frames") / "frames").glob("*.jpg"))))
    assert image is not None
    assert image.shape[:2] == (SIZE[1], SIZE[0])


def test_missing_video_raises(tmp_path: Path) -> None:
    video = tmp_path / "moved.mp4"
    video.write_bytes(b"")
    settings = {"sample_fps": 3, "target_width": 1280, "num_keyframes": 40}
    config = {"frames": {**settings, "min_sharpness_ratio": 0.5, "min_keyframe_interval_s": 1.5}}
    run = create_run("4.02", video, config, runs_root=tmp_path / "runs")
    video.unlink()  # video moved after the run was created
    with pytest.raises(UserError):
        stage.execute(run)


def test_invalid_settings_are_rejected() -> None:
    with pytest.raises(UserError):
        Settings.from_config(
            {"sample_fps": 0, "target_width": 1280, "num_keyframes": 40, "min_sharpness_ratio": 0.5}
            | {"min_keyframe_interval_s": 1.5}
        )


def test_missing_settings_are_reported_by_name() -> None:
    config = {"sample_fps": 3, "target_width": 1280, "num_keyframes": 40}
    with pytest.raises(UserError, match="min_keyframe_interval_s"):
        Settings.from_config(config | {"min_sharpness_ratio": 0.5})


def test_sharpness_ratio_above_one_is_rejected() -> None:
    config = {"sample_fps": 3, "target_width": 1280, "num_keyframes": 40}
    with pytest.raises(UserError, match="min_sharpness_ratio"):
        Settings.from_config(config | {"min_sharpness_ratio": 1.2, "min_keyframe_interval_s": 1.5})


def test_failed_rerun_leaves_no_stale_manifest(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    stage.execute(run)
    run.video.unlink()
    with pytest.raises(UserError):
        stage.execute(run)
    assert not (run.stage_dir("frames") / "frames.json").exists()


def test_frames_are_written_to_non_ascii_paths(tmp_path: Path) -> None:
    base = make_run(tmp_path)
    run = create_run("4.02", base.video, base.config, runs_root=tmp_path / "Bräunlich")
    stage.execute(run)
    data = json.loads((run.stage_dir("frames") / "frames.json").read_text(encoding="utf-8"))
    for frame in data["frames"]:
        assert frame["file"] is None or (run.stage_dir("frames") / frame["file"]).is_file()
    assert (run.stage_dir("frames") / "debug" / "keyframes.jpg").is_file()


def test_short_videos_get_fewer_keyframes(tmp_path: Path) -> None:
    run = make_run(tmp_path, min_keyframe_interval_s=2.0)  # ~9.8 s span -> 4 windows
    stage.execute(run)
    data = json.loads((run.stage_dir("frames") / "frames.json").read_text(encoding="utf-8"))
    assert data["summary"]["keyframe_windows"] == 4


@pytest.mark.parametrize(
    ("span_s", "expected"),
    [(28.0, 18), (59.9, 39), (60.0, 40), (300.0, 40), (0.5, 1)],
)
def test_keyframe_count_follows_video_length_up_to_the_cap(span_s: float, expected: int) -> None:
    settings = Settings(
        sample_fps=3,
        target_width=1280,
        num_keyframes=40,
        min_sharpness_ratio=0.5,
        min_keyframe_interval_s=1.5,
    )
    assert keyframe_count(span_s, settings) == expected


def test_floor_ratio_handles_exact_multiples() -> None:
    assert 0.6 / 0.2 < 3  # plain float division would floor to 2
    assert floor_ratio(0.6, 0.2) == 3
    assert floor_ratio(0.59, 0.2) == 2


def test_keyframes_are_sharpest_kept_frame_per_window() -> None:
    frames = [
        Frame(0, 0.0, 10.0, kept=True),
        Frame(1, 1.0, 30.0, kept=True),
        Frame(2, 2.0, 99.0, kept=False),  # sharper but dropped
        Frame(3, 3.0, 20.0, kept=True),
        Frame(4, 4.0, 5.0, kept=False),
    ]
    windows = select_keyframes(frames, 4)  # windows of 1 s: [0,1) [1,2) [2,3) [3,4]
    assert [w.index if w else None for w in windows] == [0, 1, None, 3]
    assert [f.index for f in frames if f.keyframe] == [0, 1, 3]
