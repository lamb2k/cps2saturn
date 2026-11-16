---
name: saturn-bringup
description: Getting a CPS2 port to boot and draw correctly on a real Sega Saturn. Use when a disc works on emulators but hangs, shows a black or broken picture, freezes or misbehaves on a console; for boot diagnostics from photos, register-write diffs against a known-good program, VDP2 VRAM access-cycle rules, SH-2 misalignment faults, SMPC and clock-change order, cart timing, power-up state, overscan, and the hardware test sheet.
---

# Console bring-up

Emulators forgive things a Saturn does not. Expect the first console boot to fail even when every emulator run is
clean, and plan the first hardware discs as diagnostic tools, not as releases.

## Before the first console disc

- **Diagnostics from the first instruction.** Colour bands or bit-stripe codes on screen at each boot stage, a stop
  code on fatals, and a build id on every screen that has a readout. The owner photographs the CRT; you decode the
  photo. CRT photos show diagonal shutter bands: don't read them as picture faults.
- **Rule out the disc first.** Boot a known-good homebrew disc from the same drive (optical drive emulator or burned
  CD) before blaming the program. Check IP.BIN fields and the first-read size (see `saturn-packaging`).
- **Static gates that catch what emulators don't** (all cheap, all in the build):
  - VDP2 VRAM access-cycle check (below), `tools/vdp2_cycle_check.py`.
  - Alignment gate: every 16/32-bit data symbol, pointer-cast site and on-disc structure aligned,
    `tools/align_gate.py`, with a reviewed list of cast sites.
  - Display-register latch model (see `saturn-graphics`), `tools/latch_model.py`.
- **A strict emulator copy.** Patch one emulator copy to log misaligned accesses (filter instruction-fetch noise)
  and run boot, a stage and a KO with it. Keep a positive control: a build that reintroduces a known bad access
  must show up in the log.
- Write a hardware test sheet: what to photograph, which screens, what the readout lines mean.

## Diff register writes against a known-good program

When the console misbehaves and you can't see why, compare what your program writes to the hardware with what a
program that works writes:
- Patch an emulator to log every write to VDP1, VDP2, SCU, SMPC and SCSP registers with the frame and phase.
- Log a library-initialised test program and, if you can, a shipped title, anchored at the same phase (first
  picture, first vblank of play).
- Diff. Real divergences AvP found this way: the clock change for 352-wide mode was never requested; VDP2 registers
  were left at the BIOS logo's values; the SMPC status flag was not set before writing the command register; the
  wrong SMPC command was used for the clock change.

## VDP2 VRAM access cycles

The VRAM cycle pattern registers decide which layer reads which bank in each slot. Hardware enforces the rules;
emulators mostly don't, so a wrong pattern draws fine on PC and shows shifted or dropped columns on a Saturn.
- Each layer needs its name-table reads and character reads in legal slots. Reduced (zoomed) layers need two name
  reads and two character reads, not one each.
- Character read timing must be legal for where the name read sits.
- With split banks, CPU access slots must be set in both banks, with a no-access slot before them.
- Encode the rules as a build gate and as a check over a register-write trace, with tests that known-bad words fail.
- Don't patch an emulator to "reproduce" a fault you only guessed at.

Avoid reduction where you can: a native 1:1 picture at 352 wide needs one name and one character read per layer and
leaves CPU slots open. Make it the first console control before trying a scaled picture.

## SH-2 faults emulators forgive

- Misaligned 16/32-bit reads and writes raise address errors on hardware only. One misaligned read froze a dialogue
  box on a console while every emulator ran it.
- Accesses to unmapped regions, cache-through mistakes and DMA overlap are similar. Gate them statically where you
  can, and log them in the strict emulator copy.

## Power-up and first-boot faults

- Hardware RAM is not zeroed at power-up. Test with randomised RAM contents in the emulator.
- Add read-back self-tests at boot (CRAM, VDP RAM, SCSP volume) behind a test switch. Remove them from release
  builds.
- Keep cart timing on a conservative setting, with a fallback if a verify read fails.
- A sound start can fail on a cold boot: retry it a bounded number of times.

## Overscan

CRTs crop the picture edges. HUD cells in the last column can be cut on a TV even though emulators show them whole.
Inset flush HUD rows by one cell per side, and confirm on the console.

## Reading console results

- Never write a percentage confidence from reasoning. Give what you expect for each outcome, keep a risk register
  (closed, reduced, console-only), and correct overstatements in the note itself when results come back.
- If several fixes landed in one disc, say the cause can't be separated.
- Label owner photos CONSOLE and every other number EMULATED, MODELLED or ASSUMED.

## Code in the kit

`saturn/boot/sat_diag` is the boot display that shows where a console stopped (bands per step, a code in the stripes, a red or magenta flash on failure). Use it from the first instruction of the loader.
