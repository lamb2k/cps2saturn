---
name: cps2-capture
description: MAME-side capture and reference work for CPS2-to-Saturn ports. Use for pinning MAME, golden runs (per-IRQ work RAM and object RAM dumps), saved input routes, CPS2 object lists, palettes, tile decoding, watchpoints and read taps, the program/opcode encryption split, finding the game's debug menus, and treating MAME as the behaviour reference.
---

# CPS2 capture: MAME as the reference

MAME is the ground truth for behaviour. Pin one build (the kit uses 0.289) and never mix captures from two builds.

## Set up

- Audit the set: `mame -verifyroms <set>`. Record the set name and MAME version in the config.
- Run headless for captures: `-video none -sound none -nothrottle -skip_gameinfo -autoboot_delay 0`, with
  `-keyboardprovider none -mouseprovider none -joystickprovider none -lightgunprovider none` so keys held on the
  host never reach the game (a held Ctrl is P1 button 1, and two runs of one route then differ).
- Give every run its own `-nvram_directory`, `-cfg_directory` and `-state_directory`, seeded from a known
  baseline, so a previous run's settings never leak in.
- Check free disk before a long golden; refuse to overwrite an existing capture folder.

## The encryption split

CPS2 68000 reads go through two views:
- **Opcode fetches and PC-relative operand reads** use the decrypted opcode space.
- **Absolute data reads** use the plain program space.

So a raw program dump is right for absolutely addressed tables and wrong for code and PC-relative jump tables.
Dump both spaces (`tools/mame/dump_code_spaces.lua`) and build one merged image for the lifter: program bytes, with
opcode bytes over every reachable instruction and the data it reads PC-relative.

## Goldens

A golden is the reference run the host check compares against.

- `tools/mame/golden.lua` taps the level 2 IRQ entry. At each real IRQ it writes the interrupted PC and d0-d7,
  a0-a6, then work RAM and object RAM (full, or changed words only with delta mode). It also logs every read of
  the I/O ranges so the host can replay inputs, EEPROM and sound status.
- Drive it with a saved input route (frame, button word), real ports only. No RAM pokes.
- `tools/mame_golden_run.py --config ...` builds the command line from the config; `--dry-run` prints it.
- Save MAME states at route points for later fixtures.
- Delta goldens cut size about 10x on long runs; the host reader needs the matching flag.

Routes: build them with a closed-loop bot in MAME Lua that reads RAM and presses real port bits, then save the
presses as a route. Replays of that route are deterministic.

## Object lists and tiles

- CPS2 object RAM: 8-byte entries (x, y, code, attributes). End marker in y or attributes. Multi-tile blocks use
  nx/ny fields and flip bits; coordinates are signed 10-bit and wrap.
- Decode with `tools/cps2_objects.py`: unwrap coordinates, keep tile order, flip, priority and palette bank.
- Graphics ROM tiles are 4bpp planar. `tools/cps2_tiles.py` converts to Saturn 4bpp packed pens and dedupes.
- Palettes: CPS2 palette RAM, 32 banks per layer in practice. Read it per frame from the golden or a CRAM dump.
- `screen:pixels()` is final RGB, not palette indices. Do not reverse-map colours to pens.

## Finding things

- **Actor array:** known actors a constant apart give the struct stride.
- **Script pointers:** fields in program-ROM range that advance with animation. Dump the window they walk
  (`tools/mame/dump_rom_window.lua`) and decode it as records (duration, flags, assembly pointer, offsets).
- **Writers:** watchpoints on a field show who writes it. Watchpoint PCs are skewed +2/+4 from the store.
  Never set two breakpoints at one address.
- **Bounded traces:** `bpset <entry>,<cond>,'trace file,0 ; g'` plus a frame-marker watchpoint running
  `trace off` captures one dispatch cheaply.
- **Inputs:** `tools/mame/list_inputs.lua` prints every port and field mask.

## Use the game's own debug tools

Capcom boards often keep hitbox display, collision display, spawners and info monitors. Look first. Activation is
game-specific: start in development mode with DIPs set before frame 0; if the copy to RAM was removed, write the
software switch bytes once after startup clearing. Never force cached flags every frame.

## Evidence rules

- Record for every capture: MAME build, set, route file, frames, state names, environment values and hashes.
- Keep raw captures outside git. Commit only manifests, hashes, counts and analysis code.
- Gate every capture on character identity per frame: one changed input byte can select the wrong character and
  poison every contract derived from it.
- A capture shows what happened on that route only. Census several routes (all characters, KOs, continues,
  attract) before deciding what a stage needs.
