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
RUN_SECTION = "run"  # section of the frozen config written by create_run
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
    The exact creation time (with UTC offset) is stored as `run.created`; `latest_run` sorts
    by it, because the folder name only has minute resolution and local time.
    """
    check_room_name(room)
    if RUN_SECTION in config:
        # e.g. the frozen config.yaml of an earlier run, passed as --config to repeat it
        print(f"Note: the '{RUN_SECTION}' section of the config is replaced by this run's values")
    if not video.is_file():
        raise UserError(f"video not found: {video}")
    created = (now or datetime.now()).astimezone()  # naive values are taken as local time
    timestamp = created.strftime("%Y-%m-%d_%H%M")
    root = runs_root / f"{room}_{timestamp}"
    suffix = 1
    while root.exists():
        suffix += 1
        root = runs_root / f"{room}_{timestamp}-{suffix}"
    root.mkdir(parents=True)
    run_section = {"room": room, "video": str(video.resolve()), "created": created.isoformat()}
    rest = {key: value for key, value in config.items() if key != RUN_SECTION}
    config = {RUN_SECTION: run_section, **rest}
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
    if room != room.strip():
        raise UserError(f"room name '{room}' must not start or end with whitespace")
    if any(not char.isprintable() for char in room):
        raise UserError(f"room name {room!r} must not contain control characters")
    if FORBIDDEN_ROOM_CHARS & set(room):
        forbidden = "".join(sorted(FORBIDDEN_ROOM_CHARS))
        raise UserError(f"room name '{room}' must not contain any of {forbidden}")


def load_run(root: Path) -> Run:
    if not (root / CONFIG_FILENAME).is_file():
        raise UserError(f"not a run folder (no {CONFIG_FILENAME}): {root}")
    config = load_yaml(root / CONFIG_FILENAME)
    section = config.get(RUN_SECTION)
    if not isinstance(section, dict) or not {"room", "video"} <= section.keys():
        raise UserError(
            f"not a run folder ({CONFIG_FILENAME} has no '{RUN_SECTION}' section with room "
            f"and video; create runs with: seatmap init <video> --room <name>): {root}"
        )
    return Run(root, config)


def latest_run(runs_root: Path = RUNS_ROOT) -> Run:
    """The most recently created run, by `run.created` in its config.

    Runs created before `run.created` existed fall back to the timestamp in their folder name
    (local time, minute resolution), not to the modification time of config.yaml, which
    changes whenever the file is edited. Times are compared as absolute points in time, so
    runs of different rooms in the same minute and the switch from summer to winter time are
    ordered correctly. Folders that cannot be loaded are skipped with a warning, so one broken
    run does not block commands on the others.
    """
    runs = []
    for path in runs_root.glob("*/" + CONFIG_FILENAME):
        match = RUN_NAME.search(path.parent.name)
        if match:
            try:
                run = load_run(path.parent)
                created = created_at(run, match.group(1))
            except UserError as error:
                print(f"Warning: skipping {path.parent}: {error}")
                continue
            runs.append((created, int(match.group(2) or 1), run))
    if not runs:
        raise UserError(
            f"no runs in {runs_root}; create one with: seatmap run <video> --room <name>"
        )
    return max(runs, key=lambda entry: entry[:2])[2]


def created_at(run: Run, folder_timestamp: str) -> float:
    """Creation time of a run as a POSIX timestamp.

    `folder_timestamp` is the `YYYY-MM-DD_HHMM` part of the folder name, used when the config
    has no `run.created` (runs created before it existed).
    """
    created = run.config[RUN_SECTION].get("created")
    if created is None:
        return datetime.strptime(folder_timestamp, "%Y-%m-%d_%H%M").astimezone().timestamp()
    try:
        return datetime.fromisoformat(str(created)).timestamp()
    except ValueError as error:
        raise UserError(f"run.created is not an ISO 8601 time: {created!r}") from error
