from datetime import datetime
from pathlib import Path

import pytest

from seatmap.cli import main
from seatmap.config import merge
from seatmap.errors import UserError
from seatmap.pipeline import STAGES, stage_names
from seatmap.runs import CONFIG_FILENAME, Run, create_run, latest_run, load_run


def test_merge_overrides_nested_keys_only() -> None:
    base = {"frames": {"sample_fps": 3, "target_width": 1280}, "export": {}}
    merged = merge(base, {"frames": {"sample_fps": 5}})
    assert merged == {"frames": {"sample_fps": 5, "target_width": 1280}, "export": {}}
    assert base["frames"]["sample_fps"] == 3


def make_video(tmp_path: Path) -> Path:
    video = tmp_path / "room.mp4"
    video.write_bytes(b"")
    return video


def test_create_and_load_run(tmp_path: Path) -> None:
    run = create_run(
        "4.02",
        make_video(tmp_path),
        {"frames": {"sample_fps": 3}},
        runs_root=tmp_path,
        now=datetime(2026, 11, 20, 14, 30),
    )
    assert run.root == tmp_path / "4.02_2026-11-20_1430"
    assert (run.root / CONFIG_FILENAME).is_file()
    assert run.stage_dir("frames") == run.root / "01_frames"

    loaded = load_run(run.root)
    assert loaded.room == "4.02"
    assert loaded.config["frames"]["sample_fps"] == 3


def test_cli_init_creates_run_folder(tmp_path: Path) -> None:
    default = tmp_path / "default.yaml"
    default.write_text("frames:\n  sample_fps: 3\n", encoding="utf-8")
    runs_root = tmp_path / "runs"

    args = ["init", str(make_video(tmp_path)), "--room", "4.02"]
    args += ["--default-config", str(default), "--runs-root", str(runs_root)]
    assert main(args) == 0

    (root,) = runs_root.iterdir()
    assert load_run(root).config["frames"]["sample_fps"] == 3


def test_same_minute_runs_get_a_suffix_and_latest_is_found(tmp_path: Path) -> None:
    video, now = make_video(tmp_path), datetime(2026, 11, 20, 14, 30)
    first = create_run("4.02", video, {}, runs_root=tmp_path, now=now)
    second = create_run("4.02", video, {}, runs_root=tmp_path, now=now)
    create_run("4.01", video, {}, runs_root=tmp_path, now=datetime(2026, 11, 19, 9, 0))

    assert first.root.name == "4.02_2026-11-20_1430"
    assert second.root.name == "4.02_2026-11-20_1430-2"
    assert latest_run(tmp_path).root == second.root


@pytest.mark.parametrize("room", ["", "x" * 27, "4/02"])
def test_invalid_room_names_are_rejected(tmp_path: Path, room: str) -> None:
    with pytest.raises(UserError):
        create_run(room, make_video(tmp_path), {}, runs_root=tmp_path)


def test_cli_reports_errors_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    default = tmp_path / "default.yaml"
    default.write_text("{}\n", encoding="utf-8")
    args = ["init", str(tmp_path / "missing.mp4"), "--room", "4.02"]
    args += ["--default-config", str(default), "--runs-root", str(tmp_path / "runs")]
    assert main(args) == 1
    assert main(["frames", "--runs-root", str(tmp_path / "empty")]) == 1
    output = capsys.readouterr().out
    assert "video not found" in output
    assert "no runs in" in output
    assert not (tmp_path / "runs").exists()


def test_cli_keeps_traceback_of_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(run: Run) -> None:
        raise ValueError("bug in a stage")

    monkeypatch.setitem(STAGES, "frames", broken)
    create_run("4.02", make_video(tmp_path), {}, runs_root=tmp_path / "runs")
    with pytest.raises(ValueError, match="bug in a stage"):
        main(["frames", "--runs-root", str(tmp_path / "runs")])


def test_cli_run_stops_at_first_unimplemented_stage(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[str] = []

    def done(run: Run) -> None:
        called.append("frames")

    def missing(run: Run) -> None:
        raise NotImplementedError

    monkeypatch.setitem(STAGES, "frames", done)
    monkeypatch.setitem(STAGES, "detection", missing)
    default = tmp_path / "default.yaml"
    default.write_text("{}\n", encoding="utf-8")
    args = ["run", str(make_video(tmp_path)), "--room", "4.02"]
    args += ["--default-config", str(default), "--runs-root", str(tmp_path / "runs")]

    assert main(args) == 0
    assert called == ["frames"]
    assert "Stopped: stage 'detection' is not implemented yet." in capsys.readouterr().out

    assert main(["frames", "--runs-root", str(tmp_path / "runs")]) == 0
    assert called == ["frames", "frames"]
    assert "Using latest run:" in capsys.readouterr().out

    # an explicitly requested stage that is not implemented is a failure
    assert main(["detection", "--runs-root", str(tmp_path / "runs")]) == 1
    assert main(["resume", "--until", "detection", "--runs-root", str(tmp_path / "runs")]) == 1
    assert main(["evaluate", "ref.json", "--runs-root", str(tmp_path / "runs")]) == 1


def test_stage_names_respects_start_and_stop() -> None:
    assert stage_names("detection", "topview") == ["detection", "reconstruction", "topview"]
    assert stage_names(stop="frames") == ["frames"]
    with pytest.raises(UserError):
        stage_names("layout", "frames")
