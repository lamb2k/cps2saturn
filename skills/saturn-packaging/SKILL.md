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

## Verify

- `tools/iso_verify.py IMAGE PATH --equals FILE` checks one member byte for byte and prints its hash.
- Build the package clean (no kept intermediate files), record the ISO and cue hashes, then boot from the cue
  itself, not the work folder. Run the same bytes you will hand over; rebuilding changes the hash.
- Ship a hardware test sheet (HARDWARE_TEST.md): steps, what to look for, what to send back. Hardware stays
  UNRUN until the owner runs it.

## Web test builds

A browser Saturn emulator (a libretro Yabause build in WebAssembly) can run the image for testers:
- Use the emulator's high-level BIOS. Never host a retail BIOS.
- Large images need a compressed format the core accepts; check before uploading.
- Hosting is outward-facing: it needs the owner's explicit OK, an access decision and written take-down steps.
- Note browser speed (vblanks per second) in the notes; it is not Saturn timing.

## Never commit

The package, ISO, cue, tracks, stills of game screens and the program image. Commit the build scripts, the
hardware test sheet template and the hash manifest only if it holds no game data.
