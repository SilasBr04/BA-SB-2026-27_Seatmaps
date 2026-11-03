# Recording Guide

**Status:** Draft v0.2 (Proposed), 3 Nov 2026. Based on the first pilot video
(`data/raw/pilot/test.mp4`, latest run `runs/test_2026-11-03_1653`; the video was recorded
before this guide existed and does not follow all of it, e.g. 720p). v0.2 after a review on
3 Nov. Rules marked *(unverified)* have no observed basis yet and are checked on the pilot
video of a real office room. Settle the points under "Open" before the evaluation recordings.

For the person filming one office room with a smartphone. One video = one room.

## Before recording

- **The room must be empty of people.** If someone walks in, stop and record again later.
- **Persons in reflections or behind glass count as persons in the video.** Cover mirrors.
  Watch out for glass doors, glass walls and windows to a corridor: nobody may walk past while
  recording. In the pilot video, the person filming was visible in a wall mirror.
- **Do not move any furniture.** Leave desks, chairs and screens where they normally are; do
  not turn screens away or push chairs under desks. The pipeline uses chairs and screens to
  find seats and their orientation, and the map has to show the room as it is used.
- Switch on the room lights and open the blinds, so the image is bright (less motion blur).
- Phone camera: main (1x) lens, **1080p, 30 fps** *(unverified)*. No slow motion, no
  wide-angle lens, no zoom, no filters, no HDR video *(unverified)*. Higher resolutions bring
  no benefit: frames are reduced to at most 1280 px width.
- Switch off strong stabilization modes (e.g. "Action mode") and automatic macro/lens
  switching *(unverified)*: both change the image during the video, which may disturb the
  camera motion reconstruction.
- Wipe the lens.

## Recording

- **Duration: at least 60 seconds.** The pipeline uses up to 40 keyframes and takes at most
  one per 1.5 s, so shorter videos give fewer keyframes (the 28 s pilot video gave 18 keyframe
  windows, of which 17 got a keyframe).
- **Walk slowly and turn slowly.** Fast turns smear the image; those frames are dropped. In the
  pilot video, about a quarter of the frames were dropped, almost all of them during turns.
  Rule of thumb *(unverified)*: one full turn of the camera should take at least 10 seconds.
- **Keep moving steadily.** Standing still yields near-identical frames that add no information.
- Walk **once along the walls of the room**, camera pointing roughly towards the middle of the
  room, slightly downwards so desks and the floor are in view.
- **Every desk must be fully in view at least once**, ideally from two different directions.
  Desks hidden behind others: walk into the aisle between them.
- **Every wall and corner of the room must be in view at least once**, so the room shape can
  be derived.
- Hold the phone at chest height. **Do not rotate the phone** (keep portrait or landscape for
  the whole video) and do not roll it sideways; pointing it slightly downwards is fine.
- Start and end at the door.

## After recording

- Watch the video once: no persons (also not in reflections or behind glass), every desk and
  every corner visible, no long blurry stretches.
- Name the file after the room (e.g. `4.02.mp4`) and hand it to the operator.

## For the operator

- Copy the video to `data/raw/pilot/` or `data/raw/evaluation/`. Videos are never committed
  (`data/` and video files are excluded by `.gitignore`).

## Open

- **Portrait or landscape?** The pilot video was portrait. Landscape shows more of the room
  width per frame, which may help detection and reconstruction. Decide after the stage 2/3 spike.
- **Time measurement for H1** (evaluation recordings only): recording time counts towards the
  editing time of the semi-automated path. Define when the clock starts and stops (with or
  without preparation such as lights, blinds and covering mirrors) and whether re-recordings
  are counted.
- **Screens on or off?** Switched-on screens may show personal or confidential content;
  whether screens are detected better on or off is checked in the stage 2 spike.
- **Exact walking path** for large rooms with several desk blocks: is walking into the aisles
  only where desks are hidden enough, or should the path always go through every aisle?
- Check the rules marked *(unverified)* and the duration and speed rules with a pilot video of
  a real office room.
