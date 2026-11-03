"""Command-line interface: one command per stage, plus run creation and evaluation.

Typical use:
  seatmap run data/raw/pilot/room.mp4 --room 4.02     new run, all implemented stages
  seatmap frames                                       re-run one stage on the latest run
  seatmap resume --from layout                         re-run the latest run from a stage on
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from seatmap.config import DEFAULT_CONFIG, load_config
from seatmap.errors import UserError
from seatmap.evaluation import evaluate
from seatmap.pipeline import STAGES, stage_names
from seatmap.runs import RUNS_ROOT, Run, create_run, latest_run, load_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seatmap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "run"):
        cmd = commands.add_parser(
            name,
            help="create a run folder" if name == "init" else "create a run and run the stages",
        )
        cmd.add_argument("video", type=Path, help="smartphone video of one room")
        cmd.add_argument("--room", required=True, help="room name, e.g. 4.02")
        cmd.add_argument("--config", type=Path, help="experiment config overriding the defaults")
        cmd.add_argument("--default-config", type=Path, default=DEFAULT_CONFIG)
        cmd.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
        if name == "run":
            cmd.add_argument("--until", choices=list(STAGES), help="last stage to run")

    resume = commands.add_parser("resume", help="re-run an existing run from a given stage")
    add_run_dir(resume)
    resume.add_argument("--from", dest="start", choices=list(STAGES), default="frames")
    resume.add_argument("--until", choices=list(STAGES), help="last stage to run")

    for name in STAGES:
        add_run_dir(commands.add_parser(name, help=f"run stage '{name}' on an existing run"))

    ev = commands.add_parser("evaluate", help="compare a run's layout with a reference map")
    ev.add_argument("reference", type=Path)
    add_run_dir(ev)

    return parser


def add_run_dir(cmd: argparse.ArgumentParser) -> None:
    cmd.add_argument("run_dir", type=Path, nargs="?", help="run folder (default: latest run)")
    cmd.add_argument("--runs-root", type=Path, default=RUNS_ROOT)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    complete = True
    try:
        if args.command in ("init", "run"):
            config = load_config(args.config, default=args.default_config)
            run = create_run(args.room, args.video, config, runs_root=args.runs_root)
            print(f"Run folder: {run.root}")
            if args.command == "run":
                complete = run_until(run, stage_names(stop=args.until), args.until)
        elif args.command == "resume":
            complete = run_until(open_run(args), stage_names(args.start, args.until), args.until)
        elif args.command == "evaluate":
            evaluate.execute(open_run(args), args.reference)
        else:
            complete = run_stages(open_run(args), [args.command]) == 1
    except UserError as error:
        print(f"Error: {error}")
        return 1
    except NotImplementedError as error:
        print(f"Stopped: {error}")
        return 1
    return 0 if complete else 1


def open_run(args: argparse.Namespace) -> Run:
    if args.run_dir is not None:
        return load_run(args.run_dir)
    run = latest_run(args.runs_root)
    print(f"Using latest run: {run.root}")
    return run


def run_until(run: Run, names: Sequence[str], until: str | None) -> bool:
    """Run a range of stages for `run` / `resume`; True if the command succeeded.

    With --until, every requested stage must run. Without it, the command stops at the first
    unimplemented stage and succeeds if at least one stage ran.
    """
    ran = run_stages(run, names)
    return ran == len(names) if until is not None else ran > 0


def run_stages(run: Run, names: Sequence[str]) -> int:
    """Run the stages in order; stop at the first one that is not implemented yet.

    Returns the number of stages that ran.
    """
    for done, name in enumerate(names):
        print(f"--- {name}")
        try:
            STAGES[name](run)
        except NotImplementedError:
            print(f"Stopped: stage '{name}' is not implemented yet.")
            return done
        print(f"Results: {run.stage_dir(name)}")
    return len(names)
