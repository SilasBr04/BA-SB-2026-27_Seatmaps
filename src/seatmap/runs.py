"""Run folders: one folder per pipeline run, one subfolder per stage.

Layout (see docs/technical-setup.md, section 5.3)::

    runs/<room>_<YYYY-MM-DD_HHMM>/
      config.yaml
      01_frames/ ... 07_export/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from seatmap.config import load_yaml

RUNS_ROOT = Path("runs")
CONFIG_FILENAME = "config.yaml"
DEBUG_DIRNAME = "debug"

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
    """Create a new run folder and freeze the effective config into it."""
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M")
    root = runs_root / f"{room}_{timestamp}"
    root.mkdir(parents=True, exist_ok=False)
    config = {"run": {"room": room, "video": str(video.resolve())}, **config}
    (root / CONFIG_FILENAME).write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return Run(root, config)


def load_run(root: Path) -> Run:
    return Run(root, load_yaml(root / CONFIG_FILENAME))
