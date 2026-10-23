from datetime import datetime
from pathlib import Path

from seatmap.cli import main
from seatmap.config import merge
from seatmap.runs import CONFIG_FILENAME, create_run, load_run


def test_merge_overrides_nested_keys_only() -> None:
    base = {"frames": {"sample_fps": 3, "target_width": 1280}, "export": {}}
    merged = merge(base, {"frames": {"sample_fps": 5}})
    assert merged == {"frames": {"sample_fps": 5, "target_width": 1280}, "export": {}}
    assert base["frames"]["sample_fps"] == 3


def test_create_and_load_run(tmp_path: Path) -> None:
    run = create_run(
        "4.02",
        Path("room.mp4"),
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

    args = ["init", "room.mp4", "--room", "4.02"]
    args += ["--default-config", str(default), "--runs-root", str(runs_root)]
    assert main(args) == 0

    (root,) = runs_root.iterdir()
    assert load_run(root).config["frames"]["sample_fps"] == 3
