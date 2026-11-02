"""Run folders: one folder per pipeline run, one subfolder per stage.

Layout (see docs/technical-setup.md, section 5.3)::

    runs/<room>_<YYYY-MM-DD_HHMM>/
      config.yaml
      01_frames/ ... 07_export/
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from seatmap.config import load_yaml
from seatmap.errors import UserError

RUNS_ROOT = Path("runs")
CONFIG_FILENAME = "config.yaml"
DEBUG_DIRNAME = "debug"
MAX_ROOM_NAME_LENGTH = 26  # element names <= 30 characters, minus "-T" and two digits
FORBIDDEN_ROOM_CHARS = set(r'<>:"/\|?*')
RUN_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{4})(?:-(\d+))?$")

STAGE_DIRS = {
    "frames": "01_frames",
    "detection": "02_detections",
    "reconstruction": "03_reconstruction",
    "topview": "04_topview",
    "seats": "05_seats",
    "layout": "06_layout",
    "export": "07_export",
}


@dataclass(frozen=True)
class Run:
    root: Path
    config: dict[str, Any]

    @property
    def room(self) -> str:
        return str(self.config["run"]["room"])

    @property
    def video(self) -> Path:
        return Path(self.config["run"]["video"])

    def stage_dir(self, stage: str) -> Path:
        """Output folder of a stage; created on first access."""
        path = self.root / STAGE_DIRS[stage]
        path.mkdir(parents=True, exist_ok=True)
        return path

    def debug_dir(self, stage: str) -> Path:
        """Folder for a stage's debug visualizations."""
        path = self.stage_dir(stage) / DEBUG_DIRNAME
        path.mkdir(exist_ok=True)
        return path


def create_run(
    room: str,
    video: Path,
    config: dict[str, Any],
    runs_root: Path = RUNS_ROOT,
    now: datetime | None = None,
) -> Run:
    """Create a new run folder and freeze the effective config into it.

    A second run of the same room within the same minute gets a suffix (`-2`, `-3`, ...).
    """
    check_room_name(room)
    if not video.is_file():
        raise UserError(f"video not found: {video}")
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    root = runs_root / f"{room}_{timestamp}"
    suffix = 1
    while root.exists():
        suffix += 1
        root = runs_root / f"{room}_{timestamp}-{suffix}"
    root.mkdir(parents=True)
    config = {"run": {"room": room, "video": str(video.resolve())}, **config}
    (root / CONFIG_FILENAME).write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return Run(root, config)


def check_room_name(room: str) -> None:
    if not room.strip():
        raise UserError("room name must not be empty")
    if len(room) > MAX_ROOM_NAME_LENGTH:
        raise UserError(
            f"room name '{room}' is {len(room)} characters long, "
            f"at most {MAX_ROOM_NAME_LENGTH} are allowed"
        )
    if FORBIDDEN_ROOM_CHARS & set(room):
        forbidden = "".join(sorted(FORBIDDEN_ROOM_CHARS))
        raise UserError(f"room name '{room}' must not contain any of {forbidden}")


def load_run(root: Path) -> Run:
    if not (root / CONFIG_FILENAME).is_file():
        raise UserError(f"not a run folder (no {CONFIG_FILENAME}): {root}")
    return Run(root, load_yaml(root / CONFIG_FILENAME))


def latest_run(runs_root: Path = RUNS_ROOT) -> Run:
    """The most recently created run, by the timestamp in the folder name."""
    runs = []
    for path in runs_root.glob("*/" + CONFIG_FILENAME):
        match = RUN_NAME.search(path.parent.name)
        if match:
            runs.append((match.group(1), int(match.group(2) or 1), path.parent))
    if not runs:
        raise UserError(
            f"no runs in {runs_root}; create one with: seatmap run <video> --room <name>"
        )
    return load_run(max(runs)[2])
