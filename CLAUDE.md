# CLAUDE.md

Bachelor thesis prototype: semi-automated generation of 2D office seat maps (SVG for BeSeated)
from smartphone videos of a single office room.

The full technical setup (purpose, workflow, key decisions, hardware, pipeline stages, tech
stack, open points) lives in `docs/technical-setup.md` and is imported below. Respect the
status labels there: only **Decided** items are fixed; **Proposed** and **Open** items need
confirmation before being treated as settled. Keep that file updated when decisions change.

## Code structure

- `src/seatmap/<stage>/stage.py` — one package per stage with entry point `execute(run: Run)`.
  Stages: `frames`, `detection`, `reconstruction`, `topview`, `seats`, `layout`, `export`;
  `evaluation/evaluate.py` sits outside the pipeline.
- `runs.py` — `Run` (run folder + frozen config) and `STAGE_DIRS`. A stage reads only previous
  stages' folders via `run.stage_dir(name)`, writes only to its own, and puts debug
  visualizations in `run.debug_dir(name)`.
- `pipeline.py` — ordered `STAGES` registry; `cli.py` derives one command per stage from it.
- `config.py` — `configs/default.yaml` merged with an optional experiment config; stage
  settings live under a key named after the stage.
- New stage settings go into `configs/default.yaml`; mark unconfirmed values as proposed.

## Commands

- `make test` / `make lint` (ruff + strict mypy) / `make format`
- `python -m seatmap --help`

@docs/technical-setup.md
