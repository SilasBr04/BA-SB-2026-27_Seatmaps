# Technical Setup

**Project:** Semi-automated generation of 2D office seat maps from camera recordings using AI
**Context:** Bachelor thesis, Silas Bräunlich, Provadis Hochschule (BBIM23)
**Status:** 23 Oct 2026 · v0.2 (work in progress)

Status labels used in this document: **Decided** · **Proposed** (not yet confirmed) · **Open**

---

## 1. Purpose

The prototype takes an ordinary smartphone video of **a single office room** and produces a
schematic **SVG seat map** for the booking tool BeSeated.

The map contains one room rectangle and one equally sized rectangle per bookable seat.
What matters:

- complete seat count (every seat exactly once)
- relative arrangement (rows, columns, blocks separated by aisles)
- plausible room shape

Distances, sizes and angles are normalized; metric accuracy is out of scope.
**Desks** are the target objects. **Chairs and screens** (monitors and TVs, one merged class) are
detected but not drawn; they are context indicators used to identify seats, e.g. to split a long
desk bench into several seats.

## 2. User Workflow

```
[1] Record  →  [2] Run tool in terminal  →  [3] Automatic processing
      →  [4] SVG file  →  [5] Import + correct in BeSeated editor  →  [6] Use
```

1. **Record:** A person films one office room with a smartphone, following a short recording
   guide (walk slowly, every desk in view). **No persons may appear in the video**; if someone
   does, the video is recorded again.
2. **Run:** The video is passed to the tool via a terminal command, together with the room name
   (e.g. `4.02`).
3. **Process:** The pipeline runs without user interaction (see section 5).
4. **Result:** One SVG file for the room in BeSeated style.
5. **Correct:** The SVG is imported into BeSeated; missing, wrong or misplaced seats are fixed in
   the existing BeSeated editor (human in the loop).
6. **Use:** The map is released and seats become bookable.

**Manual baseline (for evaluation):** The test person draws the room directly in the BeSeated
editor; steps 1–4 are skipped.

## 3. Key Decisions

| Topic | Decision | Status |
|---|---|---|
| Input | One video = one room | Decided |
| Output | One SVG file per room; no integration into a full floor map | Decided |
| Storage in BeSeated | Later via database with coordinates; not part of the first step | Decided |
| User interface | Terminal (CLI) only, no custom UI | Decided |
| Human in the loop | Existing BeSeated editor; no custom editor | Decided |
| Flagging uncertain results to the user | Out of scope | Decided |
| Privacy | No anonymization stage; persons are excluded by the recording guide | Decided |
| Uncertain detections | Confidence threshold; confidence values are kept in intermediate data for analysis. Threshold is tuned on pilot recordings, never on the evaluation rooms | Decided |
| Camera motion | Primary: VGGT (camera poses + depth as an aid for the 2D top view). Fallback: COLMAP | Decided |
| Time measurement (H1) | Recording time counts towards editing time of the semi-automated path; compute time is logged and reported separately | Decided |
| Language | Python | Decided |
| Compute | Everything runs locally, no cloud services | Decided |
| Getting started | Technical spike with one test video | Decided |

## 4. Hardware and Environment

### 4.1 Machines

| Machine | Specs | Role |
|---|---|---|
| GPU workstation | NVIDIA RTX 5070 (12 GB VRAM), strong CPU, 32 GB DDR5 RAM | Runs the full pipeline, model training, evaluation |
| Laptop | AMD Ryzen 5 5500U, integrated Radeon graphics (no CUDA), 16 GB RAM | Optional: coding, light stages (frame extraction, layout, SVG) |

Code is kept in sync between both machines via Git. Data and run outputs are not committed.

### 4.2 Software Environment (GPU workstation)

| Component | Choice | Notes |
|---|---|---|
| OS | Windows + **WSL2 with Ubuntu** | VGGT and COLMAP are much easier to install on Linux; CUDA works inside WSL2 |
| GPU driver | Current NVIDIA driver (installed on Windows) | Required for RTX 50 series (Blackwell) |
| CUDA / PyTorch | PyTorch build with **CUDA 12.8 or newer** | Older builds do not support the RTX 50 series |
| Python | 3.11 | |
| Package management | uv (or pip + venv) | |
| Version control | Git + GitHub | |

### 4.3 Setup Steps

1. Install the latest NVIDIA driver on Windows.
2. Enable WSL2 and install Ubuntu (`wsl --install -d Ubuntu`).
3. Inside Ubuntu: install Git, Python 3.11 and uv.
4. Clone the repository and create a virtual environment.
5. Install PyTorch with CUDA 12.8+ (from the official PyTorch index, `cu128` or newer).
6. Verify the GPU: `python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"`
7. Install the project dependencies (section 6).
8. Install VGGT from its official repository; install COLMAP (or `pycolmap`) as fallback.

## 5. Pipeline Architecture

### 5.1 Principles

- **One module per stage**, each with its own CLI command. A stage only reads the outputs of the
  previous stage(s) and writes to its own folder.
- **Every stage can be run and re-run on its own.** Errors are fixed where they occur without
  recomputing the whole pipeline.
- **Fixed file formats:** structured data as JSON with a defined schema, images as JPG, depth
  data as NumPy arrays (`.npy`), point clouds as PLY.
- **Every stage writes a debug visualization** (e.g. detections drawn on frames, top-view plot)
  for troubleshooting and as figures for the thesis.
- **One `config.yaml` per run**, copied into the run folder for reproducibility.

### 5.2 Stages

| # | Stage | Input | Output (intermediate product) | Technology |
|---|---|---|---|---|
| 1 | Frame extraction | Video + room name | Sharp frames, keyframe subset, frame list | OpenCV |
| 2 | Detection + tracking | Frames | Per frame: class (desk, chair, screen), mask, confidence, track ID | Ultralytics YOLO26-seg + tracking (BoT-SORT / ByteTrack) |
| 3 | Camera motion + depth | Keyframes | Camera poses, depth maps, point cloud | VGGT (fallback: COLMAP) |
| 4 | Top view | Outputs of 2 + 3 | Each furniture item exactly once as a 2D footprint; floor points of the room | Open3D, NumPy, shapely, scikit-learn |
| 5 | Seat derivation | Top-view objects | Seats with position and orientation; context indicators switchable (H3) | NumPy, shapely |
| 6 | Layout normalization | Seats + floor points | Room rectangle; equally sized seat rectangles on a grid with block, row, column | NumPy, scikit-learn |
| 7 | SVG export | Normalized layout | SVG file in BeSeated format | svgwrite |

Stages 2 and 3 are independent of each other.

**Outside the pipeline:** an evaluation command that compares the stage 6 output with a reference
map (seat count error, precision, recall, F1, preserved spatial relations).

### 5.3 Run Folder Layout

```
runs/4.02_2026-11-20_1430/
  config.yaml
  01_frames/
  02_detections/
  03_reconstruction/
  04_topview/
  05_seats/
  06_layout/
  07_export/room_4.02.svg
```

### 5.4 Stage 1 – Frame Extraction (Proposed)

Two consumers with different needs: detection benefits from many frames; VGGT can only process
roughly 40–50 frames at once with 12 GB VRAM. Stage 1 therefore outputs all usable frames plus a
smaller keyframe subset.

1. **Read video:** frame rate, resolution, duration and rotation metadata (smartphones often
   store rotation as metadata only).
2. **Sample frames:** e.g. 3 frames per second.
3. **Drop blurry frames:** sharpness per frame via Laplacian variance; frames clearly below the
   video's average are removed.
4. **Resize:** e.g. to 1280 px width.
5. **Select keyframes:** split the video into e.g. 40 equal time windows and take the sharpest
   frame of each.

Output in `01_frames/`: `frames/*.jpg`, `frames.json` (frame number, timestamp, sharpness,
keyframe flag, video metadata), a keyframe contact sheet and a sharpness-over-time plot.
Configurable: sampling rate, sharpness threshold, number of keyframes, target width.

Stages 2–7 will be detailed step by step.

## 6. Tech Stack

| Area | Library / Tool | Used in | Status |
|---|---|---|---|
| Deep learning framework | PyTorch (CUDA 12.8+) | 2, 3 | Decided |
| Video / image processing | OpenCV | 1, debug images | Decided |
| Object detection + tracking | Ultralytics YOLO26-seg | 2 | Decided |
| Camera poses + depth | VGGT | 3 | Decided |
| Camera poses (fallback) | COLMAP / pycolmap | 3 | Decided |
| 3D processing, floor plane | Open3D | 4 | Decided |
| Numerics | NumPy | all | Decided |
| 2D geometry | shapely | 4, 5, 6 | Decided |
| Clustering (deduplication, rows/columns) | scikit-learn | 4, 6 | Decided |
| SVG output | svgwrite | 7 | Decided |
| Data schemas | Pydantic | all | Proposed |
| Config | PyYAML | all | Proposed |
| CLI | Typer | all | Proposed |
| Evaluation (matching) | SciPy (Hungarian matching) | evaluation | Proposed |
| Analysis + plots | pandas, matplotlib | evaluation, debug | Proposed |
| Annotation for fine-tuning | Label Studio or CVAT, pre-annotation with SAM 3 | training data | Proposed |
| Testing / linting | pytest, ruff, mypy | dev | Proposed |

**Licensing note:** Ultralytics YOLO is AGPL-3.0 (fine for the thesis; a commercial use in
BeSeated would require an Enterprise license). Licenses of VGGT and SAM 3 must be checked before
any productive use.

## 7. Open Points

| Item | Clarify with | Why it matters |
|---|---|---|
| Structure of the BeSeated SVG (elements, IDs/attributes, units, sizes) | BeSeated | Determines whether the generated file can be imported directly |
| Measuring editing time and corrections in the BeSeated editor (logs available? otherwise stopwatch / screen recording) | BeSeated | Measurement data for H1 and H3 |
| Access to the three test rooms | BeSeated / office | Required for the spike and the evaluation |
| GPU workstation setup (driver, CUDA 12.8+, WSL2) | self | RTX 50 series only works with current versions |
| Update the privacy statement in the exposé (exclusion of persons instead of blurring) | supervisors | Consistency between exposé and implementation |
| Stage 1 parameters (keyframe strategy, 3 fps start value) | self | Pending confirmation |

## 8. Next Steps

1. Confirm stage 1 and detail stages 2–7.
2. Define the technical spike (test video, success criteria).
3. Define build order and timeline.
