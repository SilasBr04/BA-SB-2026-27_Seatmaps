# Stage 1 – Frame Extraction: Development Record

How stage 1 was built, which decisions were made and why. The current specification is in
[`technical-setup.md`](../technical-setup.md), section 5.4; this file records the path there.
Code: `src/seatmap/frames/`, settings: `frames` in `configs/default.yaml`.

## Problem

Two later stages consume frames, with different needs:

- **Detection (stage 2)** benefits from many frames, so every desk is seen several times and
  tracking works.
- **VGGT (stage 3)** can process only a limited number of frames at once. Originally estimated
  at about 40–50 frames for 12 GB VRAM; the 12 GB was wrong information, the workstation has
  16 GB (corrected 3 Nov, see below).

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
| 3 Nov 2026 | Code review of the branch: keyframe selection with gap changed from greedy to optimal (see below) | — |
| 3 Nov 2026 | Pilot video re-run with the optimal selection: run `test_2026-11-03_1653` | — |
| 3 Nov 2026 | Remaining code review findings fixed: settings validation, debug figures on re-run, exact threshold (see below) | — |
| 3 Nov 2026 | VRAM figure corrected: workstation has 16 GB, not 12 GB; basis of decision 10 marked as wrong | — |

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
| 10 | 40 keyframes | Chosen as the upper end that fits VGGT on 12 GB VRAM. The 12 GB was wrong information (workstation has 16 GB, corrected 3 Nov, see [`00-project.md`](00-project.md)); 40 is kept as a safe start value, the actual limit and whether more keyframes help is checked in the stage 3 spike | Proposed |
| 11 | At most one keyframe per 1.5 s (`min_keyframe_interval_s`) | Short videos would otherwise get very narrow windows and many near-identical keyframes. 40 × 1.5 s = 60 s is the cutoff; this also gives the minimum video length in the recording guide | Proposed |
| 12 | A window without a kept frame stays empty | Taking a blurry frame would give VGGT a poor image; fewer keyframes are better than bad ones. Counted in the `frames.json` summary | Implemented |
| 13 | Adjacent keyframes at least 0.75 s apart (`min_keyframe_gap_s`); a window that cannot get a keyframe without breaking the gap stays empty | Found in the pilot run (see below) | Proposed |
| 15 | With the gap, keyframes are chosen optimally over the whole video instead of greedily per window: first as many filled windows as possible, then the highest total sharpness | Code review, 3 Nov (see below) | Implemented |
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

## Code review (3 Nov): greedy keyframe selection

The first gap implementation went through the windows in order and took the sharpest allowed
frame of each. The review found that this can empty a window unnecessarily: if the sharpest
frame of window i sits at its right border, it can block every candidate of window i+1,
although a slightly less sharp frame in window i would have left room for both. Each lost
window is one VGGT slot fewer.

**Change (decision 15):** the selection is solved exactly as a longest path over the kept
frames in time order: maximize the number of filled windows first, the total sharpness second.
Without gap conflicts this gives the same result as before (the sharpest kept frame of each
window). Runtime is O(n log n) in the number of kept frames.

### Pilot run 3 (`runs/test_2026-11-03_1653`), same video, optimal selection

Same video and settings as pilot run 2 (85 sampled, 62 kept, 18 windows). Replaying the greedy
selection on this run's `frames.json` reproduces pilot run 2 exactly, so the numbers compare
directly:

| Metric | Greedy (run 2) | Optimal (run 3) |
|---|---|---|
| Keyframes / empty windows | 16 / 2 | 17 / 1 |
| Total sharpness of keyframes | 1414.5 | 1436.9 |
| Smallest gap between adjacent keyframes | 0.99 s | 0.99 s |

Findings:

1. 11 of 18 windows keep the same keyframe; the others shift to earlier frames. The extra
   window is filled with #281 (9.4 s, sharpness 37, just above the threshold of 30.5). Its
   neighbour becomes #241 (8.0 s, 54) instead of #271 (122).
2. Contact sheet: #241 and #281 show nearly the same view (chair in front of the wall mirror;
   #281 shows a little more of the doorway). So on this video the extra keyframe adds little
   new content. Both also show the person filming in the mirror (known from pilot run 1).
3. #591/#621 replace #601/#631. They are still similar views (sofa and roof window), because
   the camera barely moves there, as already seen in pilot run 2.

Conclusion: the change does what it should (one more filled window, never a smaller gap), but
on this video the gain is small, and the extra keyframe is a low-sharpness, similar view.
Whether "fill as many windows as possible" is better for VGGT than "fewer but sharper"
keyframes is checked in the stage 3 spike. Also check on a real office video.

**Rejected alternative:** keep the greedy choice and document it as a limitation. Simpler, but
it wastes keyframes exactly where blur already removed frames.

## Code review (3 Nov): smaller fixes

| Decision | Why | Status |
|---|---|---|
| `frames` settings are type-checked: numbers must be numbers, `target_width` and `num_keyframes` whole numbers (`40.0` is accepted, `40.9` is rejected instead of truncated to 40); errors name the setting | `null` or text values crashed with a Python traceback instead of a clear error, and fractional values were silently truncated | Implemented |
| A re-run deletes the old contact sheet and sharpness plot before it starts, like `frames.json` | After a failed re-run the figures of the previous run stayed in `debug/` and could be taken for figures of the current settings | Implemented |
| `frames.json` reports the exact (unrounded) sharpness threshold; the mean is computed once | The threshold was rounded to 2 decimals for the report but frames were compared with the unrounded value, so a dropped frame could appear to lie above the reported threshold | Implemented |

Second review (3 Nov):

| Decision | Why | Status |
|---|---|---|
| A run config without a `frames` section is reported as a user error | `run.config["frames"]` raised a `KeyError` traceback before the check meant to report a missing section could run | Implemented |
| `select_keyframes` first clears all keyframe flags, then flags its choice; the result per window is read from the flags (no matching by `id()`) | Called twice on the same frames, flags from the first call survived, so the keyframe count and contact sheet would include stale keyframes | Implemented |
| The contact sheet prints a warning for a keyframe file that is missing or unreadable | It was skipped silently, so the sheet could show fewer tiles than keyframes without any hint | Implemented |
| Not changed: blurry frames are still written to disk first and deleted after the threshold is known; the contact sheet re-reads keyframes from disk | The threshold depends on the mean sharpness of all frames, so avoiding the writes would mean either keeping all encoded frames in memory or decoding the video twice. The cost (one JPEG write per dropped frame, 40 reads for the sheet) is small compared with stages 2 and 3 | Proposed |

Re-running stage 1 on pilot run 3 after the first review's fixes gave the same frames and keyframes;
only the reported threshold changed from 30.52 to 30.5218 (unrounded).

## Open

- Confirm the start values (3 fps, 1280 px, 40 keyframes, ratio 0.5, interval 1.5 s, gap
  0.75 s) with a pilot video of a real office room.
- Number of keyframes depends on the VGGT memory check in the stage 3 spike.
