---
name: saturn-packaging
description: Packaging Saturn builds of CPS2 ports. Use for building the ISO data track and cue with CDDA audio tracks, IP.BIN boot header fields, the 80-minute CD-R sector budget, the shared sector store that dedupes round files, verifying ISO members and hashes, hardware test sheets, and web test builds through a browser Saturn emulator.
---

# Saturn packaging

## Layout

- Track 1: MODE1/2048 data track (ISO-9660): IP.BIN boot header, the program, cold code, round files or the store.
- Tracks 2+: CDDA, 44.1 kHz stereo 16-bit, 2-second pregap each.
- The cue names raw tracks `BINARY`; burn tools and optical drive emulators read them as audio in that byte order.
- `tools/make_cue.py` writes the cue from a data image and a folder of track files, plus `SHA256SUMS.txt` with the
  commit (a `#` line, which `sha256sum -c` skips).

## ODE package verification

- Check the supported CUE and data-track formats for the target optical drive emulator (ODE) and firmware. Record the
  data mode, track count and number of files. A CUE that mounts in a software emulator can still fail on the target ODE.
- Verify every CUE `FILE` entry resolves to the intended file in the delivered package, including the spelling and
  extension. Honor the target's directory and path rules. When staging to an SD card, verify the manifest against the
  files read back from the card.
- For a new mixed-mode layout, keep a one-track boot control ready. In a separate test folder, reference the same data
  track from a CUE with only track 1 in its original mode and index. Confirm the data-track hash. Cold-boot the exact
  final mixed-mode package and verify CDDA playback on the target before accepting its hardware results.
  See [boot isolation](../saturn-bringup/SKILL.md#isolate-ode-boot-failures).

## IP.BIN

Check the fields you depend on before patching: IP size at 0xE0 (0x1800 for a stock header), first-read load
address at 0xF0, read size at 0xF4 (0 means "the first file's length"), and any embedded copy of the load address.
`tools/ip_bin.py` checks and patches them, and fails if the header has an unexpected shape.

## The CD-R budget

An 80-minute CD-R holds 360,000 sectors (74 min: 333,000). Count data sectors, audio sectors (bytes / 2352) and
150 sectors per pregap. `tools/disc_budget.py` reports it.

AvP went over (about 372,500 sectors) with 210 per-stage round files plus 26 music tracks. The fix was not cutting
music: round files repeat most of their sectors, so:

## Shared sector store

Store every unique 2 KB sector of all round files once, in one `STORE.BIN`, with a run table per round (store
sector, count). Reading a round's runs in order gives its file back byte for byte, so the loader walks it as
before. Data sectors go in first-use order so each round's reads stay mostly sequential. AvP: data track 240,771
to 94,143 sectors, all 210 rounds byte-identical. `tools/sector_store.py` builds and verifies it.

## Loading

- **Read count is the limit, not drive speed.** AvP's stage loads were dozens of small region reads, each paying a
  command and a seek. Coalesce adjacent reads and read boot files in disc order.
- Compression: deflate does well on tile and code data (about 0.5 to 0.65 of the size); byte-LZ barely helps 4-bit
  tiles. The SH-2 decode (about 70 clocks a byte) is the bound, so overlap decode with the next read. Expect a modest
  gain (AvP: about 1 s off an 8 s load).
- Prove in-place decode fits for every file at build time, and refuse files that don't.
- Emulators charge a flat seek time, so seek-order gains only show on hardware.

## Loader corruption

A read-coalescing change corrupted 157 of AvP's 287 stage files, and the self-check missed it: a rotating XOR
cancels over overlapping regions. So:
- Use a multiplicative checksum.
- Replay the loader offline over every file (`tools/loader_replay.py`), with a control that runs the old loader and
  proves the tool sees the bug.
- Keep an in-game self-test over all files behind a test switch.

## Build hygiene

- A build tool that reuses an object because it is newer than its source will keep stale code when only the flags
  change. Key objects on the flag set, or delete them when flags change.
- Each source file is compiled with one flag family. A switch passed in the wrong family is silently ignored, so
  check the switch reached the object (symbols or a string).
- ISO volume dates differ on every build. Byte-identity checks compare members and the store, not the whole image.
- Kept intermediates carry receipts (hashes of inputs, layout, packer and outputs); a mismatch forces a rebuild.

## Verify

- `tools/iso_verify.py IMAGE PATH --equals FILE` checks one member byte for byte and prints its hash.
- Build the package clean (no kept intermediate files), record the ISO and cue hashes, then boot from the cue
  itself, not the work folder. Run the same bytes you will hand over; rebuilding changes the hash.
- Ship a hardware test sheet (HARDWARE_TEST.md): steps, what to look for, what to send back. Hardware stays
  UNRUN until the owner runs it.

## Web test builds

A browser Saturn emulator (a libretro Yabause build in WebAssembly) can run the image for testers:
- Use the emulator's high-level BIOS. Never host a retail BIOS.
- Large images need a compressed format the core accepts (CHD worked), split into parts if the uploader has a size
  limit, with a manifest holding the parts and the whole-file hash. Upload parts first and the manifest last, and
  keep a copy of the previous manifest as the rollback.
- Hosting is outward-facing: it needs the owner's explicit OK, an access decision and written take-down steps.
- Note browser speed (vblanks per second) in the notes; it is not Saturn timing.

## Never commit

The package, ISO, cue, tracks, stills of game screens and the program image. Commit the build scripts, the
hardware test sheet template and the hash manifest only if it holds no game data.

## Code in the kit

`saturn/boot/`, `saturn/cd/` and `saturn/ld/` have the loader side: boot display, clock change, 4 MB cart bring-up, GFS file loads, the sector store reader that matches `tools/sector_store.py`, an in-place deflate decoder and the link script templates.
