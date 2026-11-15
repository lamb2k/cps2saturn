# Trailer or reveal video: checklist

Short checklist for one looping clip of a port. The tools are `tools/clip/shot_script.py` (capture) and
`tools/video/assemble.py` plus `tools/video/mix.py` (edit and sound). Method notes: `skills/clip-capture`,
`skills/video-assemble`. Copy this file into the lane's work folder and tick it as you go.

## Before you start

- [ ] Owner's brief: length, platforms (named only as export preset names), what must be shown, claims allowed.
- [ ] Storyboard: one row per shot with the scene, the route to it and the caption.
- [ ] Which shots are staged (health hold, saved state) and which can be poke-free. Release media must be poke-free.

## Capture disc

- [ ] Build the release commit and recipe in your own work folder with the debug readouts compiled out. Change nothing else.
- [ ] Keep the disc image and its ELF together; write commit, flags and build log path into a CAPTURE-DISC.md.
- [ ] Boot it once and look at a screenshot: no readout.

## Clips

- [ ] One spec per clip; start from a working one. `p:` screenshots after every route step.
- [ ] Waits on game state (`idle`, `ge`, `in`, `need` conditions), never on a fixed time after a load.
- [ ] Keep each clip's saved state; retake from it. A replayed route gives different pictures.
- [ ] Look at the first, middle and last picture of each take and read its take.json.
- [ ] `--smooth` number per take, for the hand-back.
- [ ] A glitch is retaken once, then reported with its frame folder. It is not edited out.

## Edit

- [ ] `--probe` for the crop; `--sheet`; `--draft`; fix in-points so the action lands in each shot.
- [ ] Captions are true of the captured build. Staged assists are disclosed (`shot_script.py --disclose`).
- [ ] Corner tag says what the footage is (for example "Emulator capture").
- [ ] Sound: take audio aligned (report the alignment error), music ducked, voices placed, loudness target met.
- [ ] Final render. Report has no problems; loop seam under about 12.

## Hand back

- [ ] Output paths, the contact sheet, which clips were staged and how, any fallback used, any caption changed and why,
      what could not be verified.
- [ ] Nothing posted, nothing uploaded. The owner posts.
