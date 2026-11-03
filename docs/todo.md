# To-do: what is needed before each stage can be programmed

Things only you can do (record, decide, set up, ask BeSeated). Once the items of a stage are
done, Claude can implement that stage. Decisions go into `technical-setup.md` afterwards.

## 0. Setup

- [x] Commit the current doc changes (`technical-setup.md`, `beseated-map-format.md`, this file)
- [x] Laptop: install dev dependencies (`uv pip install -e ".[dev]"`), check `make test` runs
- [x] GPU workstation: driver, WSL2 + Ubuntu, Python 3.11, uv, clone repo (section 4.3)
- [x] GPU workstation: PyTorch with CUDA 12.8+, verify the GPU with the check in step 6 of section 4.3
- [x] GPU workstation: install VGGT and COLMAP / pycolmap

## 1. Frame extraction — implemented, needs a pilot video to tune

- [x] Stage implemented (`python -m seatmap frames <run_dir>`), tested on a synthetic video
- [x] Run it on the pilot video and check `01_frames/debug/` (contact sheet, sharpness plot)
- [x] Add a minimum gap between adjacent keyframes (pilot run showed near-duplicates)
- [x] Code review fixes: optimal instead of greedy keyframe selection, "latest run" by exact
      creation time, CLI exit code when no stage ran
- [x] Re-run the pilot video with the new keyframe selection and compare with pilot run 2
      (pilot run 3: 17 instead of 16 keyframes, the extra one is a similar, less sharp view)
- [ ] Stage 3 spike: compare VGGT with all filled windows vs. only the sharper keyframes
- [x] Remaining code review findings: `run` section in configs, type checks for `frames`
      settings, run folder check, old debug images on failed re-runs, exact threshold
- [x] Second code review: latest-run fallback by folder name, broken run folders skipped,
      YAML errors as user errors, room name whitespace, stale keyframe flags
- [x] Confirm the two review findings left unchanged (evaluate argument order, writing
      blurry frames before dropping them), see development/00-project.md and 01-frames.md
- [x] Confirm the start values: 3 fps, 1280 px width, 40 keyframes, sharpness ratio 0.5,
      minimum keyframe interval 1.5 s, minimum keyframe gap 0.75 s
- [x] Write a short recording guide: draft in `recording-guide.md`
- [x] Review the recording guide (v0.2, 3 Nov)
- [ ] Recording guide: give reasons for, or check on the office pilot video, the rules marked
      *(unverified)* (10 s per turn, 30 fps, no HDR, no wide-angle, stabilization off)
- [ ] Recording guide: decide portrait vs. landscape and screens on/off after the stage 2/3 spike
- [ ] Record a pilot video of a real office room (several desks), following the guide
- [x] Record 1–2 pilot videos of a room that is **not** an evaluation room; put them in
      `data/raw/pilot/`

## 2. Detection + tracking — needs the pilot video

- [ ] Run the spike: pretrained YOLO26-seg on pilot frames, look at the debug images
- [ ] Decide: are pretrained classes good enough (desk ≈ "dining table", "chair", "tv"),
      or is fine-tuning needed?
- [ ] If fine-tuning: choose Label Studio or CVAT, annotate pilot frames (desk, chair, screen)
- [ ] Choose model size (n / s / m) and tracker (BoT-SORT or ByteTrack) based on the spike

## 3. Camera motion + depth — needs the pilot video and the workstation

- [ ] Run VGGT on the 40 pilot keyframes; check that it fits into 16 GB VRAM (and whether more keyframes fit) and the poses look plausible
- [ ] Check the VGGT license
- [ ] Decide whether the COLMAP fallback is needed

## 4. Top view — needs results of 2 + 3

- [ ] Look at the spike output together (point cloud, detections) and agree on how desks are
      projected to the floor and merged across frames

## 5. Seat derivation — needs your domain rules

- [ ] Define what counts as a seat (desk alone? desk + chair? desk + screen?)
- [ ] Define how a long desk bench is split (e.g. one seat per 1.6 m, or per chair/screen)
- [ ] Decide which tables are **not** bookable (meeting tables, standing desks, …)

## 6. Layout normalization — needs a few decisions

- [ ] Confirm the scale: one desk = 40 × 20 units (≈ 25 units per metre)
- [ ] Define the seat numbering order for `T<n>` (e.g. row by row from the top left)
- [ ] Confirm: room is always drawn as one rectangle (no L-shapes)

## 7. Export — can start now

- [ ] Provide `floor` values for the config (placeholders are fine for now:
      `locationId`, floor `name`, `number`, `main`, `type`)

## Evaluation — needs BeSeated

- [ ] Get access to the three test rooms
- [ ] Draw the manual baseline maps in the BeSeated editor and fetch them via
      `GET /BeSeated/api/locations/{locationId}/floors/{floorId}/floor-distributions`
      into `data/reference/`
- [ ] Define when a generated seat "matches" a reference seat (distance tolerance)

## BeSeated / thesis

- [ ] Clarify who builds the import of the map file into the backend, and when
      (needed for the user study, H1/H3)
- [ ] Clarify how editing time and corrections are measured (logs, stopwatch, screen recording)
- [ ] Define when the recording time starts and stops for H1 (with or without preparation,
      re-recordings counted?) and add it to the recording guide
- [ ] Update the exposé: output is a BeSeated map file (JSON), not an SVG; privacy by
      excluding persons instead of blurring
