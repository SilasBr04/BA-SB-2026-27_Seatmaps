# seatmap-gen

Semi-automated generation of 2D office seat maps from camera recordings using AI.

## Purpose

This project is part of a bachelor thesis. A smartphone video of **one office room** is turned
into a schematic seat map for the booking tool BeSeated (a JSON file with BeSeated entity
records plus an SVG preview), where it is corrected in the existing editor. Full technical description: [`docs/technical-setup.md`](docs/technical-setup.md).

Pipeline (one module and one CLI command per stage, each re-runnable on its own):

| # | Stage | Module | Output folder |
|---|---|---|---|
| 1 | Frame extraction | `seatmap.frames` | `01_frames/` |
| 2 | Detection + tracking | `seatmap.detection` | `02_detections/` |
| 3 | Camera motion + depth | `seatmap.reconstruction` | `03_reconstruction/` |
| 4 | Top view | `seatmap.topview` | `04_topview/` |
| 5 | Seat derivation | `seatmap.seats` | `05_seats/` |
| 6 | Layout normalization | `seatmap.layout` | `06_layout/` |
| 7 | Export | `seatmap.export` | `07_export/` |

Evaluation against reference maps (`seatmap.evaluation`) runs outside the pipeline.

## Folder overview

```
configs/            default.yaml + experiment configs (override only changed keys)
data/
  raw/pilot/        Pilot recordings (threshold tuning)          — never committed
  raw/evaluation/   Recordings of the evaluation rooms           — never committed
  annotations/      Annotations for fine-tuning
  reference/        Reference seat maps for evaluation
docs/               Technical setup, recording guide, BeSeated map format
  development/      Development record per stage: decisions and why
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

The virtual environment `.venv` is not committed; create it once per machine. Installing the
project (`-e`) puts the `seatmap` command into the venv, so it is only available while the venv
is active.

**Linux / WSL2 (with [uv](https://docs.astral.sh/uv/)):**

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"                     # light stages + dev tools

# GPU workstation only:
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
uv pip install -e ".[gpu,dev]"
# VGGT without its pinned dependencies, so the cu128 PyTorch build is kept:
git clone https://github.com/facebookresearch/vggt.git ~/vggt
uv pip install --no-deps -e ~/vggt
uv pip install huggingface_hub einops safetensors pillow
uv pip install -e ".[dev,gpu,colmap]"          # COLMAP fallback (pycolmap)
```

**Windows (PowerShell, without uv):** install Python 3.11 first
(`winget install --id Python.Python.3.11 -e`), then in the project folder:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1                     # prompt shows (.venv)
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
seatmap --help                                 # check
```

If activation fails with "running scripts is disabled", run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

**PyCharm:** select `.venv\Scripts\python.exe` (or `.venv/bin/python`) as the project
interpreter (Settings → Project → Python Interpreter). Do not let PyCharm create its own venv:
it may pick a different Python version and does not install the project.

**Tests and linting:** `make test`, `make lint`, `make format` and `make install` work on
Linux/WSL2. Windows has no `make`; run the commands directly in the active venv:

```powershell
pytest                                         # make test
ruff check src tests; ruff format --check src tests; mypy src tests   # make lint
ruff check --fix src tests; ruff format src tests                     # make format
```

## Working on the GPU workstation (WSL2)

The GPU stages run in Ubuntu inside WSL2, in a separate clone of the repository in the Linux
home folder (`~/BA-SB-2026-27_Seatmaps`), not in the Windows copy under `C:\Users\...`.

**Get in, every time:**

1. Open Ubuntu: Start menu → "Ubuntu", or type `wsl` in PowerShell / Windows Terminal.
2. Go to the project and activate the venv:

   ```bash
   cd ~/BA-SB-2026-27_Seatmaps
   source .venv/bin/activate                    # prompt shows (BA-SB-2026-27_Seatmaps)
   git pull                                     # get changes pushed from Windows / the laptop
   ```

3. Optional check that the GPU is visible:

   ```bash
   python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```

Leave Ubuntu with `exit`. WSL shuts down on its own after a while; `wsl --shutdown` in
PowerShell stops it immediately (e.g. to free RAM).

**Moving files between Windows and Ubuntu:**

- Windows drives are mounted in Ubuntu under `/mnt/c/...`. Raw videos are not in Git, so copy
  them into the WSL clone:

  ```bash
  mkdir -p ~/BA-SB-2026-27_Seatmaps/data/raw
  cp -r /mnt/c/Users/silas/PycharmProjects/BA-SB-2026-27_Seatmaps/data/raw/pilot ~/BA-SB-2026-27_Seatmaps/data/raw/
  ```

- From Windows, the Ubuntu files are in Explorer under `\\wsl$\Ubuntu\home\silas\` (also
  listed as "Linux" in the sidebar), e.g. to look at debug images in `runs/`.
- Do not work on the project directly under `/mnt/c`: file access across the mount is slow.

Code moves between the two clones only via Git (commit + push on one side, `git pull` on the
other).

## Usage

Whole pipeline:

```bash
seatmap run data/raw/pilot/room.mp4 --room 4.02                  # new run, all stages
seatmap run data/raw/pilot/room.mp4 --room 4.02 --until frames   # new run, stop after a stage
```

Single stages, on the latest run (or pass a run folder, e.g. `runs/4.02_2026-11-20_1430`):

```bash
seatmap init data/raw/pilot/room.mp4 --room 4.02   # new run folder only, no stage
seatmap frames                                     # (re-)run one stage
seatmap resume --from topview                      # re-run from a stage onwards
seatmap resume --from detection --until topview    # re-run a range of stages
seatmap evaluate data/reference/4.02.json          # compare with a reference map
```

`run` stops with a message at the first stage that is not implemented yet. Add
`--config configs/<experiment>.yaml` to `run`/`init` to override defaults. Without activating
the virtual environment, use `python -m seatmap` instead of `seatmap`.

## Privacy

Never commit raw videos. There is no anonymization stage: persons are excluded by the recording
guide, and a video in which a person appears is recorded again.
