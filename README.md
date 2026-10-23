# seatmap-gen

Semi-automated generation of 2D office seat maps from camera recordings using AI.

## Purpose

This project is part of a bachelor thesis. A smartphone video of **one office room** is turned
into a schematic **SVG seat map** for the booking tool BeSeated, where it is corrected in the
existing editor. Full technical description: [`docs/technical-setup.md`](docs/technical-setup.md).

Pipeline (one module and one CLI command per stage, each re-runnable on its own):

| # | Stage | Module | Output folder |
|---|---|---|---|
| 1 | Frame extraction | `seatmap.frames` | `01_frames/` |
| 2 | Detection + tracking | `seatmap.detection` | `02_detections/` |
| 3 | Camera motion + depth | `seatmap.reconstruction` | `03_reconstruction/` |
| 4 | Top view | `seatmap.topview` | `04_topview/` |
| 5 | Seat derivation | `seatmap.seats` | `05_seats/` |
| 6 | Layout normalization | `seatmap.layout` | `06_layout/` |
| 7 | SVG export | `seatmap.export` | `07_export/` |

Evaluation against reference maps (`seatmap.evaluation`) runs outside the pipeline.

## Folder overview

```
configs/            default.yaml + experiment configs (override only changed keys)
data/
  raw/pilot/        Pilot recordings (threshold tuning)          — never committed
  raw/evaluation/   Recordings of the evaluation rooms           — never committed
  annotations/      Annotations for fine-tuning
  reference/        Reference seat maps for evaluation
docs/               Technical setup
runs/               One folder per run: runs/<room>_<YYYY-MM-DD_HHMM>/
notebooks/          Exploratory Jupyter notebooks
src/seatmap/        Python package
  cli.py            CLI entry point (`seatmap ...`)
  config.py         Config loading and merging
  runs.py           Run folder layout
  pipeline.py       Ordered stage registry
  <stage>/stage.py  One package per stage, entry point `execute(run)`
tests/              Test suite
```

## Setup

Requires Python 3.11. The full pipeline runs on the GPU workstation in WSL2 (Ubuntu); the light
stages also run on a machine without CUDA. See `docs/technical-setup.md`, section 4.

```bash
uv venv --python 3.11
source .venv/bin/activate                      # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"                     # light stages + dev tools

# GPU workstation only:
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install -e ".[gpu,dev]"
# VGGT: install from its official repository; COLMAP fallback: uv pip install -e ".[colmap]"
```

`make install`, `make test`, `make lint` and `make format` are available as well.

## Usage

```bash
seatmap run data/raw/pilot/room.mp4 --room 4.02          # new run, all stages
seatmap init data/raw/pilot/room.mp4 --room 4.02         # new run folder only
seatmap detection runs/4.02_2026-11-20_1430              # (re-)run a single stage
seatmap resume runs/4.02_2026-11-20_1430 --from topview  # re-run from a stage onwards
seatmap evaluate runs/4.02_2026-11-20_1430 data/reference/4.02.svg
```

Add `--config configs/<experiment>.yaml` to `run`/`init` to override defaults.

## Privacy

Never commit raw videos. There is no anonymization stage: persons are excluded by the recording
guide, and a video in which a person appears is recorded again.
