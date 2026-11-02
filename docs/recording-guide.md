# Recording Guide

**Status:** Draft v0.1 (Proposed), 2 Nov 2026. Based on the first pilot video
(`data/raw/pilot/test.mp4`, run `runs/test_2026-11-02_1153`). Settle the points under "Open"
before the evaluation recordings.

For the person filming one office room with a smartphone. One video = one room.

## Before recording

- **The room must be empty of people.** If someone walks in, stop and record again later.
- **Cover mirrors and switch on or turn away reflective screens if possible.** Persons visible
  in a mirror, glass door or switched-off monitor count as persons in the video. In the pilot
  video, the person filming was visible in a wall mirror.
- Switch on the room lights and open the blinds, so the image is bright (less motion blur).
- Phone camera: main (1x) lens, **1080p or higher, 30 fps**. No slow motion, no wide-angle
  lens, no zoom, no filters, no HDR video.
- Wipe the lens.

## Recording

- **Duration: at least 60 seconds.** The pipeline uses up to 40 keyframes and takes at most
  one per 1.5 s, so shorter videos give fewer keyframes (the 28 s pilot video gave only 16).
- **Walk slowly and turn slowly.** Fast turns smear the image; those frames are dropped. In the
  pilot video, about a quarter of the frames were dropped, almost all of them during turns.
  Rule of thumb: one full turn of the camera should take at least 10 seconds.
- **Keep moving steadily.** Standing still yields near-identical frames that add no information.
- Walk **once along the walls of the room**, camera pointing roughly towards the middle of the
  room, slightly downwards so desks and the floor are in view.
- **Every desk must be fully in view at least once**, ideally from two different directions.
  Desks hidden behind others: walk into the aisle between them.
- Hold the phone at chest height and keep it upright; do not tilt it while filming.
- Start and end at the door.

## After recording

- Watch the video once: no persons (also not in reflections), every desk visible, no long
  blurry stretches.
- Name the file after the room (e.g. `4.02.mp4`) and copy it to `data/raw/pilot/` or
  `data/raw/evaluation/`. Never commit videos.

## Open

- **Portrait or landscape?** The pilot video was portrait. Landscape shows more of the room
  width per frame, which may help detection and reconstruction. Decide after the stage 2/3 spike.
- **Exact walking path** for large rooms with several desk blocks (along the walls only, or
  also through the aisles).
- Check the duration and speed rules with a pilot video of a real office room.
