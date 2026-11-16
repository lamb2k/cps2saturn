# Tools

Game-neutral tools. Game constants come from `configs/<set>.yaml` (`--config`). None of them contains game
data. Their outputs are derived from your game: write them outside git.

Run the smoke tests with `python -m unittest discover -s tests -v`. They use synthetic data only.

| Tool | Area | What it does |
| --- | --- | --- |
| `cfg.py` | all | Loads the per-game config (PyYAML or a built-in reader), expands `${ENV}` values |
| `boards.py` | all | Board facts from `game.board` (`cps2` default, `cps1`, `cpsdash`): opcode view, where the object table lives, its size; config values override |
| `hygiene_scan.py` | repo | Pre-push scan: blocked file types, size, binary content, private paths, tokens, keys |
| `mame/golden.lua` | capture | Golden run: per-IRQ registers + work RAM + object RAM (full or delta), I/O log, route playback, state saves. On CPS-1 and CPS-Dash it taps the program space (no opcode view) and follows the object base register |
| `mame_golden_run.py` | capture | Runs MAME with `golden.lua` from the config; seeds `nvram/` and `cfg/` from baselines; `--dry-run` prints the command |
| `golden_reader.py` | capture, host check | Reads full or delta goldens; shows changed words; finds the first difference between two |
| `mame/dump_code_spaces.lua` | capture | Dumps the program and decrypted opcode views over a range (program only on CPS-1 and CPS-Dash) |
| `mame/dump_rom_window.lua` | capture | Dumps one program-space window (script tables) |
| `mame/list_inputs.lua` | capture | Prints every input port and field, for the config's route bits |
| `dis68k.py` | game logic | Bounded 68000 disassembly, vectors and cross references (capstone) |
| `cps2_objects.py` | graphics | Decodes CPS2 object lists; tile funnel stats per frame over a golden |
| `cps2_tiles.py` | graphics | CPS2 4bpp planar tiles to Saturn 4bpp, deduped, SGP1 pack |
| `page_plan.py` | graphics, memory | Shared pages, keep and restore sets, ranked tile drops per stage file |
| `sector_store.py` | packaging | One shared store of unique 2 KB sectors for all round files, verified byte for byte |
| `disc_budget.py` | packaging | Data + CDDA + pregap sectors against an 80- or 74-minute CD-R |
| `make_cue.py` | packaging | Cue for data track + CDDA tracks, SHA256SUMS with the commit |
| `iso_verify.py` | packaging | Lists ISO-9660 members or checks one against its source |
| `ip_bin.py` | packaging | Checks and patches IP.BIN boot fields with read-back |
| `yaba_mcp.py` | testing | Yabasanshiro MCP client, port owner check, own-window pad input |
| `audio_compare.py` | audio | Emulator audio capture against a MAME reference: offset, envelope correlation, level |

Not ported, and why: [NOT-PORTED.md](NOT-PORTED.md).

## Platform tree tools

Tools that go with `saturn/` (see `saturn/README.md`).

| Tool | Area | What it does |
| --- | --- | --- |
| `fn_heat.py` | SH-2 timing | Per function heat from a profiling emulator's dumps and a link map; keys are `object:symbol` and survive a relink |
| `place_plan.py` | SH-2 timing | Hot code placement: which functions go in the fast RAM within a byte budget, where the cold ones go, as linker include lists |
| `opx_store.py` | game logic | Builds and reads the opcode range store `saturn/rt/sat_opx.c` looks up |
| `saturn_build_check.py` | SH-2 build | Compiles every `saturn/` module with your SH-2 compiler, warnings as errors; says SKIP without one |

## Hardware gates

Checks for what emulators forgive and a console does not. Each exits 0 pass, 1 fail, 2 bad input, and takes its
inputs from files, never from a game header.

| Tool | Area | What it does |
| --- | --- | --- |
| `vdp2_cycle_check.py` | graphics | VDP2 VRAM access-cycle rules from a JSON/YAML spec or a register-write trace: name and cell read counts per layer (reduced layers need 2+2), legal cell timing for the name timing, split-bank CPU slots with a no-access slot in front |
| `align_gate.py` | SH-2 build | 2/4-byte alignment of data symbols from nm output, literal offsets of wide accessors, and a reviewed list of pointer-cast sites; emulators allow what the SH-2 faults on |
| `latch_model.py` | SH-2 timing | Exhaustive interleaving model of a publish/apply protocol: a per-register latch mixes old and new values, a sequence-word snapshot never does |
| `loader_replay.py` | loading | Replays a JSON read plan (coalesced or not) over files into a memory model; compares final regions with sequential loading; multiplicative checksum, because a rotating xor cancels over overlapping regions |
| `lookdiff.py` | testing | Pixel diff of two stills or two folders: changed-pixel share, bounding box, masks, a limit for gating, optional A / B / diff image; stdlib PNG, Pillow optional |
| `hygiene_scan.py --history` | repo | Scans every blob reachable from any ref (deleted files stay in history) for blocked types, size, private paths and keys; `--allow-media` or `.hygiene-media` names folders where owner-approved release media may live |

## Environment values the MAME scripts read

`golden.lua`: `CPS2SAT_OUT`, `CPS2SAT_IRQ_TAP`, `CPS2SAT_IRQ_VECTOR`, `CPS2SAT_WORK`, `CPS2SAT_OBJ`, `CPS2SAT_OBJ_REG`,
`CPS2SAT_IO`, `CPS2SAT_MAXIRQ`, `CPS2SAT_DELTA`, `CPS2SAT_ROUTE`, `CPS2SAT_ROUTE_BITS`, `CPS2SAT_LAST`, `CPS2SAT_SAVE`.
`mame_golden_run.py` sets all of them from the config. `CPS2SAT_OBJ_REG` is set only when the object table follows
a register (CPS-1, CPS-Dash); the run then also writes `golden.bin.obj.txt`, one `irq base` line (hex base) each
time the table moves, giving the first record that uses the new base.

`dump_code_spaces.lua`: `CPS2SAT_FIRST`, `CPS2SAT_LAST`, `CPS2SAT_OUT_PROGRAM`, `CPS2SAT_OUT_OPCODES`.
`dump_rom_window.lua`: `CPS2SAT_FIRST`, `CPS2SAT_LAST`, `CPS2SAT_SPACE`, `CPS2SAT_OUT`.

## Route files

One line per change: `frame word`, where bit i of the word is entry i of `inputs.route_bits`. Optional
`last N` line ends the run. Real ports only.

## Clips and video

Game-neutral capture and edit tools. Capture constants live in the config's `capture:` section (see
`configs/avspu.example.yaml`). Optional packages: Pillow, numpy, imageio-ffmpeg. Each tool stops with a clear message when
one it needs is missing, and its smoke test skips. Frames, audio and videos are derived from your game: keep them out of
git. Nothing here uploads anything. Methods: `skills/clip-capture`, `skills/video-assemble`; checklist:
`playbook/templates/TRAILER.md`.

| Tool | Area | What it does |
| --- | --- | --- |
| `clip/shot_script.py` | capture | Route and take language (wait, repeat, tap, hold, press, idle, save/load state, step, need conditions), paused one-frame stepping, per-chunk `take.json`, own emulator copy only, staged assists logged; `--dry-run`, `--disclose` |
| `clip/align_audio.py` | audio | Cuts a real-time audio recording to a stepped take: vblank clock fit, median event-to-onset latency, alignment error report |
| `video/assemble.py` | video | JSON edit list to 1080p mp4: 4:3 picture in a 16:9 frame, punch-ins, captions, cards, loop dissolve, named export presets, contact sheet; `--probe`, `--smooth` |
| `video/mix.py` | audio | Sound track for the edit list: game-sound cuts, ducked music, voice lines, loudness target |
