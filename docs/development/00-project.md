# Project-wide Decisions: Development Record

Decisions that are not tied to one stage, how they came about and why. The current state is in
[`technical-setup.md`](../technical-setup.md), sections 1–4 and 6. Reasons are only filled in
where they were written down; "—" means the reason still has to be recorded.

## Timeline

| Date | Step | Commit |
|---|---|---|
| 23 Oct 2026 | Project start: technical setup v0.2, repository skeleton (one package per stage, run folders, CLI) | `5167f51` |
| 26 Oct 2026 | Technical setup v0.3: output changed from SVG to the BeSeated map format (JSON) | `ff1c0ea` |
| 2 Nov 2026 | Stage 1 implemented ([`01-frames.md`](01-frames.md)) | `ff2d1b9` |
| 3 Nov 2026 | Hardware specs corrected: the GPU workstation has an RTX 5060 Ti with 16 GB; the earlier "RTX 5070, 12 GB" was wrong information | — |
| 3 Nov 2026 | Code review of the stage 1 branch: "latest run" lookup and CLI exit codes fixed (see below) | — |
| 3 Nov 2026 | Code review, remaining findings: `run` section of configs and run folder check (see below) | — |

## Scope and workflow

| Decision | Why | Status |
|---|---|---|
| One video = one office room | — | Decided |
| Terminal (CLI) only, no custom UI | — | Decided |
| Corrections in the existing BeSeated editor (human in the loop), no custom editor | — | Decided |
| Flagging uncertain results to the user is out of scope | — | Decided |
| Metric accuracy out of scope; what counts is seat count, relative arrangement, plausible room shape | — | Decided |
| Desks are the target objects; chairs and screens are detected only as context indicators (e.g. to split a desk bench into seats) | — | Decided |
| Recording time counts towards the editing time of the semi-automated path; compute time is reported separately (H1) | — | Decided |
| Start with a technical spike on one test video | — | Decided |

## Output format: from SVG to the BeSeated map format

**v0.2 (23 Oct):** the tool would produce one SVG per room "in BeSeated style"; storage in the
BeSeated database was planned for later. The structure of the BeSeated SVG was an open point.

**v0.3 (26 Oct):** the BeSeated map format was described from the backend
([`beseated-map-format.md`](../beseated-map-format.md)). Finding: a BeSeated map is **not** an
SVG but a list of `FloorDistribution` records (axis-aligned rectangles). So:

| Decision | Why | Status |
|---|---|---|
| Output is one map file per room in the BeSeated map format (JSON); SVG only as a preview | That is the format the backend imports and the editor works on | Decided |
| The tool never writes to the BeSeated database; the file is imported in a separate step | — | Decided |
| Reference maps for the evaluation are fetched from the BeSeated API in the same format | So the evaluation compares like with like | Proposed |
| Scale of existing maps (desk = 40 × 20 units) | BeSeated draws text and icons at fixed sizes in map units | Proposed |

Details and the consequences for stages 6 and 7: `technical-setup.md`, section 5.5.

## Privacy

| Decision | Why | Status |
|---|---|---|
| No anonymization stage; persons are excluded by the recording guide, a video with a person is recorded again | — | Decided |
| Reflections (mirrors, glass, switched-off screens) count as persons | Pilot run 1: the person filming was visible in a mirror ([`01-frames.md`](01-frames.md)) | Proposed |

The exposé still describes blurring; it has to be updated (`todo.md`).

## Technology and environment

| Decision | Why | Status |
|---|---|---|
| Python | — | Decided |
| Everything runs locally, no cloud services | — | Decided |
| VGGT for camera poses and depth, COLMAP as fallback | — | Decided |
| Ultralytics YOLO26-seg for detection and tracking | — | Decided |
| GPU workstation runs Windows + WSL2 with Ubuntu | VGGT and COLMAP are much easier to install on Linux; CUDA works inside WSL2 | Decided |
| PyTorch with CUDA 12.8 or newer | Older builds do not support the RTX 50 series | Decided |
| Confidence threshold for detections, tuned on pilot recordings only, never on evaluation rooms | — | Decided |
| Fixed file formats per stage (JSON, JPG, `.npy`, PLY), one module and CLI command per stage, debug output per stage, frozen `config.yaml` per run | Every stage can be re-run on its own; runs are reproducible; debug images help troubleshooting and serve as thesis figures | Decided |

**GPU workstation specs corrected (3 Nov):** up to v0.3 the setup listed the GPU workstation as
an RTX 5070 with 12 GB VRAM. **That was wrong information, not a hardware change:** the machine
was never a 12 GB machine. Checked on the machine itself (`nvidia-smi`, system info): NVIDIA
GeForce RTX 5060 Ti with 16 GB VRAM (Blackwell, driver 621.01), AMD Ryzen 7 7800X3D, 32 GB
DDR5-4800, Windows 11 Pro.

Consequences:

- Still RTX 50 series, so the CUDA 12.8+ requirement is unchanged.
- Everything sized for 12 GB was based on the wrong value. In particular the VGGT estimate of
  40–50 frames at once, and with it the choice of 40 keyframes in stage 1
  ([`01-frames.md`](01-frames.md), decision 10). With 16 GB more keyframes may fit; the actual
  limit is measured in the stage 3 spike.

## Run folders and CLI: fixes from the code review (3 Nov)

| Decision | Why | Status |
|---|---|---|
| Each run stores its exact creation time with UTC offset (`run.created` in `config.yaml`); "latest run" (stage commands without a run folder) is chosen by it, not by the folder name. Older runs without it fall back to the modification time of their `config.yaml` | The folder name only has minute resolution and local time: two rooms started in the same minute were ordered alphabetically, and after the switch to winter time a newer run could sort before an older one, so a stage could silently re-process the wrong room | Implemented |
| `seatmap run` / `resume` without `--until` fail (exit code 1) if not a single stage ran; with `--until` every requested stage must run | `resume --from detection` returned 0 although nothing was computed, while `seatmap detection` returned 1 for the same situation; scripts would treat it as success | Implemented |
| The `run` section of a run's config is always written by the tool: a `run` section in the default or experiment config is replaced (with a note on the console), not merged | A `run:` key in an experiment config silently overwrote the room and video, and the stage then crashed. It is replaced rather than rejected, so the frozen `config.yaml` of an earlier run can be passed as `--config` to repeat an experiment | Implemented |
| A folder only counts as a run folder if its `config.yaml` has a `run` section with room and video | A copy of `configs/default.yaml` in a folder was accepted and failed later inside the stage with a traceback | Implemented |

**Licensing note:** Ultralytics YOLO is AGPL-3.0 (fine for the thesis, commercial use in
BeSeated would need an Enterprise license). VGGT and SAM 3 licenses still to be checked.
