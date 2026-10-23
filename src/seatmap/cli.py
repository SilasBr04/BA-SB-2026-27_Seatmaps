"""Command-line interface: one command per stage, plus run creation and evaluation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from seatmap.config import DEFAULT_CONFIG, load_config
from seatmap.evaluation import evaluate
from seatmap.pipeline import STAGES, run_all
from seatmap.runs import RUNS_ROOT, create_run, load_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seatmap", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "run"):
        cmd = commands.add_parser(
            name,
            help="create a run folder" if name == "init" else "create a run and run all stages",
        )
        cmd.add_argument("video", type=Path, help="smartphone video of one room")
        cmd.add_argument("--room", required=True, help="room name, e.g. 4.02")
        cmd.add_argument("--config", type=Path, help="experiment config overriding the defaults")
        cmd.add_argument("--default-config", type=Path, default=DEFAULT_CONFIG)
        cmd.add_argument("--runs-root", type=Path, default=RUNS_ROOT)

    resume = commands.add_parser("resume", help="re-run an existing run from a given stage")
    resume.add_argument("run_dir", type=Path)
    resume.add_argument("--from", dest="start", choices=list(STAGES), default="frames")

    for name in STAGES:
        cmd = commands.add_parser(name, help=f"run stage '{name}' on an existing run")
        cmd.add_argument("run_dir", type=Path)

    ev = commands.add_parser("evaluate", help="compare a run's layout with a reference map")
    ev.add_argument("run_dir", type=Path)
    ev.add_argument("reference", type=Path)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command in ("init", "run"):
        config = load_config(args.config, default=args.default_config)
        run = create_run(args.room, args.video, config, runs_root=args.runs_root)
        print(run.root)
        if args.command == "run":
            run_all(run)
    elif args.command == "resume":
        run_all(load_run(args.run_dir), start=args.start)
    elif args.command == "evaluate":
        evaluate.execute(load_run(args.run_dir), args.reference)
    else:
        STAGES[args.command](load_run(args.run_dir))
    return 0
