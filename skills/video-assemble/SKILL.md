---
name: video-assemble
description: Assemble captured PNG frame folders into a looping 1080p video from a JSON edit list - 4:3 game picture in a 16:9 frame, punch-ins, captions, cards, music ducking, game sound, voice lines, loudness target, loop dissolve, named export presets, contact sheet and checks. Use to cut, re-cut or export footage of a port, or any emulator frame captures.
---

# Edit list to video

`tools/video/assemble.py` reads an edit list (EDL, JSON), composes every output picture in Python and encodes with
ffmpeg. No editor, no window. `tools/video/mix.py` builds the sound track from the same list. Optional packages:
Pillow (pictures), numpy (sound), imageio-ffmpeg (a bundled ffmpeg; a system ffmpeg on PATH works too). A missing one
stops the tool with a message saying what to install.

```
python tools/video/assemble.py EDL.json --sheet    # contact sheet and report only
python tools/video/assemble.py EDL.json --draft    # half size, fast: check the cut
python tools/video/assemble.py EDL.json            # final: master and the export presets
python tools/video/assemble.py --probe FRAME_DIR   # the game picture's box inside a capture, for "crop"
python tools/video/assemble.py --smooth FRAME_DIR  # distinct pictures per 60 in a capture
python tools/video/mix.py EDL.json                 # sound track: <title>_mix.wav, then "audio_mix" in the EDL
```

## What it writes (in the EDL's `out` folder)

| File | What |
| --- | --- |
| `<title>_1080p60_master.mp4` | near-lossless master |
| `<title>_<preset suffix>.mp4` | one per export preset (default `web60`, `web30`, `silent60`) |
| `<title>_sheet.png` | first, middle and last picture of every clip: read it before and after each render |
| `<title>_first.png`, `_last.png`, `_poster.png` | loop ends and thumbnail |
| `<title>_report.json` | clip table, problems, loop seam value, file sizes |

Export presets are named dicts in `EXPORT_PRESETS` (fps, bitrate, max rate, buffer, GOP, audio on or off). Add or
replace some with `export_presets` in the EDL and list the ones to write in `exports`. They are generic by design: check each
platform's own current limits before you upload, since this skill does not.

## Edit list

The full key list is at the top of `tools/video/assemble.py`. In short:

- **Timeline** is in pictures at `fps`. Each clip has `at` and `dur`; later clips draw over earlier ones.
- **Source** is a folder of PNGs (`src`, relative to `shots_root`), start picture `in`, `speed` (0.5 = half speed, 0 = freeze).
- **Framing:** `pillar` shows the whole 4:3 picture with a blurred copy of itself at the sides; `fill` covers 16:9 and
  crops top and bottom (`anchor_y`); `punch` animates a zoom window `{from: [cx, cy, zoom], to: [...]}`.
- **Captions** on the whole timeline (`captions`) or inside a clip; `tags` are small corner labels such as "Emulator capture".
- **Font:** the EDL's `font` path, else `$VIDEO_FONT`, else a search of the system font folders, else Pillow's default.
- **Audio** items start at a picture number; `cdda: true` reads a raw CD track. For game sound, music and voices use
  `mix.py` and point `audio_mix` at its output. Its take layout is `<shots_root>/<take>/aligned.wav` (sample 0 = start of
  picture 0, from `tools/clip/align_audio.py`) beside the take's pictures.
- **Loop:** `loop_bridge: 12` dissolves the last 12 pictures into picture 0. Make the last shot end on the first shot's
  framing so only text changes.
- **Stand-in:** with `standin` set, a clip whose folder is missing uses that folder and is listed under problems, so a
  draft cut works before every clip exists.

## Method

1. `--probe` one capture folder and put the box in the EDL's `crop` (all clips share it when the capture window size was
   the same).
2. `--sheet`, read the sheet, fix the obvious.
3. `--draft`, then look at pictures where it matters: use the sheet, or pull single pictures by setting `poster_frame`.
4. Adjust `in` so the hit, flash or pose lands in the shot; keep cuts on action.
5. Mix the sound (`mix.py`), check its report (loudness after, true peak), set `audio_mix`.
6. Final render. Check the report: `problems` must be empty and `loop_seam_mean_abs_diff` under about 12.

## Rules

- The picture is shown at 4:3 (`display_aspect`), as on a TV. Do not stretch it to 16:9.
- Do not hide a glitch with an edit; report it.
- **Captions must be true of the captured build.** A staged capture (a health hold, a placed enemy) is disclosed in the
  caption or the hand-back; `tools/clip/shot_script.py --disclose` lists what was staged.
- **Release media comes from the release build** with no memory pokes, and debug readouts compiled out, never hidden by
  a crop or a layer.
- Label emulator footage as emulator footage (a corner tag). Footage from the emulator proves nothing about console speed.
- **Outputs stay local.** These tools never upload. Nothing leaves the PC without the owner's OK.
