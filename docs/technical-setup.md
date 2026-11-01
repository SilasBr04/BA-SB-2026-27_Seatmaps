# Technical Setup

**Project:** Semi-automated generation of 2D office seat maps from camera recordings using AI
**Context:** Bachelor thesis, Silas Bräunlich, Provadis Hochschule (BBIM23)
**Status:** 26 Oct 2026 · v0.3 (work in progress)

Status labels used in this document: **Decided** · **Proposed** (not yet confirmed) · **Open**

---

## 1. Purpose

The prototype takes an ordinary smartphone video of **a single office room** and produces a
schematic seat map for the booking tool BeSeated: a **map file in the BeSeated map format**
(JSON with one record per room and desk, see 5.5) plus an SVG preview.

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
      →  [4] JSON file  →  [5] Import + correct in BeSeated editor  →  [6] Use
```

1. **Record:** A person films one office room with a smartphone, following a short recording
   guide (walk slowly, every desk in view). **No persons may appear in the video**; if someone
   does, the video is recorded again.
2. **Run:** The video is passed to the tool via a terminal command, together with the room name
   (e.g. `4.02`).
3. **Process:** The pipeline runs without user interaction (see section 5).
4. **Result:** One JSON file with the room's BeSeated entities, plus an SVG preview.
5. **Correct:** The JSON is imported into the BeSeated backend (separate step); missing, wrong or misplaced seats are fixed in
   the existing BeSeated editor (human in the loop).
6. **Use:** The map is released and seats become bookable.

**Manual baseline (for evaluation):** The test person draws the room directly in the BeSeated
editor; steps 1–4 are skipped.

## 3. Key Decisions

| Topic | Decision | Status |
|---|---|---|
| Input | One video = one room | Decided |
| Output | One map file per room in the BeSeated map format (section 5.5); SVG only as preview; no integration into a full floor map | Decided |
| Storage in BeSeated | The map file is imported into the backend in a separate step; the tool never writes to the BeSeated database | Decided |
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
| 7 | Export | Normalized layout | JSON with BeSeated entity records; SVG preview | Pydantic, svgwrite |

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
  07_export/room_4.02.json
  07_export/room_4.02.svg      (preview)
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

### 5.5 BeSeated Map Format (target of stages 6 + 7)

The output format is defined by the BeSeated backend in
[`beseated-map-format.md`](beseated-map-format.md) (file format, field rules, JSON Schema,
geometric conventions). The file is imported into the backend; importing is a separate step
outside the tool.

**Key facts:**

- A BeSeated map is **not** an SVG. It is a list of `FloorDistribution` records per floor
  (rooms, desks, …), each an axis-aligned rectangle.
- Desks are not linked to rooms; a desk belongs to a room only because it lies inside the room's
  rectangle and is drawn on a higher layer (`z`).
- Coordinates: origin top-left, y downwards, `x`/`y` = top-left corner, integers ≥ 0.

**What the tool produces (Decided):** one map file per room,
`07_export/room_<room name>.json`: a `floor` object plus `distributions` with one `ROOM` and one
`TABLE` per bookable seat. The fields that carry the result are `name`, `shape`, `type`, `x`,
`y`, `width`, `height`; all other required fields get the convention values below so the file is
schema-valid, and are adjusted later in the app if needed.

| Field | `ROOM` | `TABLE` |
|---|---|---|
| `name` | Room name from the CLI | `<room name>-T<n>`, n = table number (e.g. `FFM-4OG-4.01-T8`) |
| `shape` | `Viereck` | `Viereck` |
| `x`, `y` | `0`, `0` | Top-left corner, inside the room |
| `width` × `height` | From the layout | `40 × 20` or `20 × 40` |
| `z` | `0` | `2` |
| `reservable`, `requestable`, `locked` | `false`, `false`, `false` | `true`, `true`, `false` |
| `owner`, `notification`, `icons` | `null`, `null`, `[]` | `null`, `null`, `[]` |

The `floor` object (`locationId`, `name`, `number`, `main`, `type`) is unknown to the tool and
comes from the `export` section of the config (placeholders for the experiment, Proposed).
Naming is low priority for the experiment; for later use on whole floors, the tool asks for a
floor name and uses it as the prefix instead of the room name.

**Consequences for the pipeline (Proposed):**

- **Stage 6 – axis alignment:** the room is rotated so its main axis lines up with x/y. A seat's
  orientation is expressed only by choosing `40 × 20` or `20 × 40`.
- **Stage 6 – scale:** units have no fixed meaning, but BeSeated draws text and icons at fixed
  sizes in map units, so the map must use the scale of existing maps: one desk = 40 × 20 units
  (roughly 25 units per metre for a 1.6 m desk), rooms about 115–121 wide. Values are rounded
  to integers.
- **Stage 6 – geometry rules:** every `TABLE` lies completely inside the `ROOM`, desks do not
  overlap (touching edges are allowed), and a strip of about 15 units at the top of the room is
  kept free for the room name.
- **Name length:** element names ≤ 30 characters, so the room name may be at most 26 characters
  (`-T` plus two digits); the CLI rejects longer names.
- **Stage 7 – validation:** the file is checked against the JSON Schema and the geometric
  conventions (format document, sections 6–8) before it is written.
- **Evaluation:** reference maps of the manual baseline are fetched in the same format via
  `GET /BeSeated/api/locations/{locationId}/floors/{floorId}/floor-distributions`, so the
  evaluation compares like with like.

**SVG preview (stage 7, debugging and thesis figures only):** drawn from the same records the
way BeSeated draws them: the `viewBox` is the bounding box of all elements, one `<rect>` per
element painted in ascending `z` (room below desks), the room name as text at (5, 12) inside
the room, and the tool's own seat numbers on the desks.

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
| SVG preview | svgwrite | 7 | Decided |
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
| Import of the map file into the BeSeated backend (who builds it, when) | BeSeated | Without it the map cannot be corrected in the editor, so H1/H3 cannot be measured |
| `floor` values for the test rooms (`locationId`, floor name and number) | BeSeated | Needed for a schema-valid file; placeholders until then |
| Measuring editing time and corrections in the BeSeated editor (logs available? otherwise stopwatch / screen recording) | BeSeated | Measurement data for H1 and H3 |
| Access to the three test rooms | BeSeated / office | Required for the spike and the evaluation |
| GPU workstation setup (driver, CUDA 12.8+, WSL2) | self | RTX 50 series only works with current versions |
| Update the privacy statement in the exposé (exclusion of persons instead of blurring) | supervisors | Consistency between exposé and implementation |
| Stage 1 parameters (keyframe strategy, 3 fps start value) | self | Pending confirmation |

## 8. Next Steps

1. Confirm stage 1 and detail stages 2–7.
2. Define the technical spike (test video, success criteria).
3. Define build order and timeline.
