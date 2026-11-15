---
name: clip-capture
description: Frame-exact gameplay clips of a Saturn port from your own emulator copy, as PNG sequences. Use for trailers, comparison clips and any footage of the port - the route and take language, paused one-picture-at-a-time stepping, waiting on the game's own state, staged assists and how to disclose them, retakes from a saved state, and optional real-time audio alignment.
---

# Frame-exact clip capture

`tools/clip/shot_script.py` starts your own emulator copy on a disc, plays a route to the scene, then captures takes with
the core paused: one emulated frame per PNG. Host load cannot drop or repeat pictures. The game's constants live in the
`capture:` section of the per-game config (`configs/avspu.example.yaml` shows the keys; the numbers are yours to fill
from your own MAME and emulator work).

```
python tools/clip/shot_script.py --config configs/<set>.yaml SPEC.json --dry-run   # checks the spec and the ini changes, starts nothing
python tools/clip/shot_script.py --config configs/<set>.yaml SPEC.json
python tools/clip/shot_script.py --disclose <out>                                  # the staged assists, as plain sentences
```

Output: `<out>/route/NN_label.png` (route screenshots), `<out>/<take id>/f000000.png ...`,
`<out>/<take id>/take.json` (keys, vblank and player state per chunk, build, assists), `<out>/assists.json`,
`<out>/capture.log`. Run it in the background; a route plus a few hundred pictures takes minutes.

## Rules

- **Your own emulator copy only.** Copy the emulator folder, put an empty `.capture-copy` file in it, point
  `capture.emulator_dir` at it. The tool writes only that copy's ini, refuses the user's own settings folder, and checks
  that the MCP port belongs to the process it started. One instance per lane, one port each. Never start, kill or edit
  another lane's or the owner's emulator.
- **Never global input.** Keys go to the emulator's own window handle by PostMessage, or through the bridge's pad tool
  (`capture.pad_mode: mcp`, a patched build). No window activation, no typing into the desktop.
- **Label the window.** The tool titles it with the clip name and port. Re-check after a relaunch.
- **Silent by default.** Capture runs with the core's sound off. Sound is laid in afterwards (see `video-assemble`).
- **Frames and discs stay on this PC,** out of git. Nothing leaves the PC without the owner's OK.

## Spec

A JSON file: `name`, `cue` (and `elf` of the same build, for `sym:NAME` addresses), `out`, `build` (free text: commit and
flags), `window` (the same size for every clip so all pictures share one crop), `slot` (state saved when the route
ends), `route`, `takes`. Route steps and take keys are listed at the top of `tools/clip/shot_script.py`:
wait (`w`, `r`), tap (`t`), hold (`h`), press and release, `idle`, `hp`, `save`/`load`, `step`, memory waits (`ge`, `in`),
need conditions (`need0`, `need1`, `needeq`), and `{"repeat": N, "steps": [...]}` blocks.

## Method

1. **Wait on the game's own state, not on time.** Every wait counts the game's vblank counter or reads its memory.
   Loads vary between builds and hosts; a fixed wait after a load lands on the wrong screen or gets the player killed.
   Use `idle` to wait for the player to stand free, `ge`/`in` to wait for a flag, and `need` conditions to abort a
   capture that landed in the wrong place (the caller retries).
2. **Write the route with `p:` screenshots after every step,** run it, and look at the screenshots before capturing.
3. **When the route lands, keep the saved state** and iterate on the take's schedule alone. Each take reloads the state.
4. **Retake from the saved state.** Replaying a route does not give the same pictures twice: key timing in the
   free-running part varies. A retake that must match an earlier one starts from the same state.
5. **Capture more than the edit needs,** half a second each side.
6. **Check a take** by looking at its first, middle and last picture and at `take.json` (the state column shows whether
   an action came out). Measure the picture rate with `python tools/video/assemble.py --smooth <take folder>` (60 = a new
   picture every frame) and put the number in the hand-back.
7. **Hold health only when staged, and say so.** `hp:N` and a take's `health` write the player's health word. They are
   staging assists: allowed, logged in `take.json` and `assists.json`, and every caption or hand-back that uses the
   footage discloses them (`--disclose` prints the sentences). Do not let an assist stand in for play that the build
   cannot do on its own.
8. **Release media comes from the release build** with no memory pokes: no health set, no state edited. Use a staged
   capture for development clips and a poke-free capture for anything published as the release.
9. **Debug readouts are compiled out, never hidden.** Capture a build made without the frame counter and profiler
   overlays (change nothing else), not a window cropped or a layer toggled off. Boot it once and look at a screenshot.
10. **Captions must be true of the captured build.** The emulator is not the console: a speed or hardware claim needs
    the evidence tier that supports it (see `emulator-testing`).
11. **Do not hide a glitch with an edit.** If a picture shows a missing sprite or garbage tiles, retake once; if it
    repeats, report it with the frame folder, since it may be a real bug.

## Optional: real-time audio alignment

A stepped take is silent. To lay the game's sound under it, replay the take in real time with sound on, record the
emulator's audio and poll (wall time, vblank, state) in the same loop, then run `tools/clip/align_audio.py`. It fits the
vblank clock, measures the median delay from state-change events to the first sound onset, and cuts the recording so
sample 0 is the start of picture 0. The spread of the per-event deviations is the alignment error to quote. An exact
alternative needs a patched emulator that dumps the sound chip's output in emulated time (not in this kit: see
`tools/NOT-PORTED.md`).

## Limits

- The emulator is not the console. Timing-accurate claims come from the console or from a strict emulator, not from
  these clips.
- Two-player clips need a bridge with a pad tool that takes a second pad.
