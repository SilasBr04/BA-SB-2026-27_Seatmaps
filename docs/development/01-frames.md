# Stage 1 – Frame Extraction: Development Record

How stage 1 was built, which decisions were made and why. The current specification is in
[`technical-setup.md`](../technical-setup.md), section 5.4; this file records the path there.
Code: `src/seatmap/frames/`, settings: `frames` in `configs/default.yaml`.

## Problem

Two later stages consume frames, with different needs:

- **Detection (stage 2)** benefits from many frames, so every desk is seen several times and
  tracking works.
- **VGGT (stage 3)** can process only about 40–50 frames at once with 12 GB VRAM.

Smartphone videos also bring practical problems: rotation stored only as metadata, variable
frame rate, motion blur during turns, and different resolutions per phone.

**Decision:** stage 1 outputs all usable frames for detection plus a smaller keyframe subset
for VGGT.

## Timeline

| Date | Step | Commit |
|---|---|---|
| 23 Oct 2026 | Project skeleton: stage packages, run folders, CLI | `5167f51` |
| 2 Nov 2026 | Stage 1 implemented, tested on a synthetic video | `ff2d1b9` |
| 2 Nov 2026 | First pilot video (home room, 28 s, portrait): run `test_2026-11-02_1144` | — |
| 2 Nov 2026 | Minimum gap between adjacent keyframes added; re-run `test_2026-11-02_1153`; recording guide drafted | — |

## Decisions

| # | Decision | Why | Status |
|---|---|---|---|
| 1 | Sample at a fixed rate (3 fps) instead of using every frame | 30 fps videos have nearly identical neighbouring frames; 3 fps keeps enough overlap for tracking at a tenth of the data | Proposed |
| 2 | Decode sequentially, do not seek | Seeking is unreliable for phone videos (variable frame rate, keyframe-based codecs) | Implemented |
| 3 | Timestamps from the video's presentation times | Phones record with variable frame rate; `index / fps` drifts | Implemented |
| 4 | Let OpenCV apply the rotation metadata, store frames upright, record the angle | Later stages need upright images; the angle stays available for analysis | Implemented |
| 5 | Resize to 1280 px width, downscale only | Enough detail for detection, smaller files; upscaling adds no information | Proposed |
| 6 | Sharpness = variance of the Laplacian on the resized grayscale frame | Standard, fast blur measure; computing it after resizing makes values comparable between videos of different resolution | Implemented |
| 7 | Drop frames below 0.5 × the video's mean sharpness | A relative threshold adapts to each video's lighting and texture; an absolute value would have to be tuned per room | Proposed |
| 8 | Keep dropped frames in `frames.json` (`kept: false`, no image file) | Allows analysing how much was dropped and where | Implemented |
| 9 | Keyframes: split the video into equal time windows, take the sharpest kept frame of each | Spreads keyframes over the whole walk (all parts of the room) while preferring sharp frames | Proposed |
| 10 | 40 keyframes | Upper end that fits VGGT on 12 GB VRAM; to be checked in the stage 3 spike | Proposed |
| 11 | At most one keyframe per 1.5 s (`min_keyframe_interval_s`) | Short videos would otherwise get very narrow windows and many near-identical keyframes. 40 × 1.5 s = 60 s is the cutoff; this also gives the minimum video length in the recording guide | Proposed |
| 12 | A window without a kept frame stays empty | Taking a blurry frame would give VGGT a poor image; fewer keyframes are better than bad ones. Counted in the `frames.json` summary | Implemented |
| 13 | Adjacent keyframes at least 0.75 s apart (`min_keyframe_gap_s`); a window whose kept frames are all too close stays empty | Found in the pilot run (see below) | Proposed |
| 14 | Debug output: keyframe contact sheet and sharpness-over-time plot | Quick visual check per run; usable as thesis figures | Implemented |

## Pilot run 1 (`runs/test_2026-11-02_1144`)

Video: home room (not an evaluation room), 28.3 s, 720 × 1280 portrait, rotation 90°.

| Metric | Value |
|---|---|
| Sampled / kept / dropped | 85 / 62 / 23 (27 % dropped) |
| Keyframe windows / keyframes | 18 / 17 (1 window without a sharp frame) |
| Sharpness threshold | 30.5 (mean 61.0) |

Findings:

1. Rotation and the "no upscaling" rule worked: frames upright, kept at 720 px width.
2. Dropped frames come in two blocks (about 5.5–8 s and 9.5–11.5 s), where the camera turned
   quickly. The 0.5 ratio removes clearly smeared frames; the fix is slower recording, not a
   different threshold.
3. **Near-duplicate keyframes:** three pairs only 0.3–0.7 s apart (#271/#281, #371/#381,
   #601/#621). Cause: the sharpest frame of two neighbouring windows can lie right at their
   shared border. This wastes scarce VGGT slots → decision 13.
4. The person filming is visible in a wall mirror → recording guide: reflections count as
   persons.
5. 28 s gives only 18 of 40 possible windows → recording guide: at least 60 s.
6. The room has only one desk; it is enough to tune stage 1, but the detection spike needs a
   pilot video of a real office.

## Pilot run 2 (`runs/test_2026-11-02_1153`), with `min_keyframe_gap_s: 0.75`

| Metric | Value |
|---|---|
| Keyframe windows / keyframes | 18 / 16 (2 empty windows) |
| Smallest gap between adjacent keyframes | 0.99 s (before: 0.33 s) |

The duplicates #281, #381 and #621 are gone. In their place come #411 (desk and chair from a
new angle) and #631; one window stays empty because its only sharp frame was a duplicate.
#601/#631 still look alike, because the camera barely moved during that second. A time-based
rule cannot detect that; it is covered by the recording guide ("keep moving steadily").

**Rejected alternative:** compare image content (e.g. histogram or feature similarity) to find
duplicates. More precise, but adds a second tunable threshold; the time gap solves the observed
problem with one parameter. Revisit if VGGT results suffer from redundant keyframes.

## Open

- Confirm the start values (3 fps, 1280 px, 40 keyframes, ratio 0.5, interval 1.5 s, gap
  0.75 s) with a pilot video of a real office room.
- Number of keyframes depends on the VGGT memory check in the stage 3 spike.
