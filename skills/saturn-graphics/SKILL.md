---
name: saturn-graphics
description: Saturn graphics for CPS2 ports. Use for converting CPS2 sprites to VDP1 and scroll layers to VDP2, the 4bpp 16x16 tile baseline, palettes to CRAM, 384-to-352 crop and scaling, HUD placement, translucency and colour calculation, VDP1 command budgets, the slave SH-2 draw split, and planning cart pages and per-stage round files with drop ranking when tiles do not fit.
---

# Saturn graphics for CPS2 ports

## The baseline

- **Sprites to VDP1.** One VDP1 command per visible 16x16 tile, 4bpp with a colour bank. Cull off-screen and
  fully transparent tiles before emitting. Keep tile order, flip and priority from the object list.
- **Scroll layers to VDP2.** CPS2 scroll 1 (8x8 text), scroll 2 (16x16) and scroll 3 (32x32) map to NBG layers.
  Row scroll where the game uses it.
- **Palettes to CRAM.** Convert CPS2 colour words at load or on change, per bank. Count live banks per frame; refuse
  cleanly when over capacity rather than drawing wrong colours.
- **Tile pens:** CPS2 pen 15 is transparent. Remap so Saturn pen 0 is transparent (`p -> p + 1`, 15 -> 0).
  `tools/cps2_tiles.py` does this and dedupes identical payloads.

Measure before choosing more complex schemes (row merging, cel composition). `tools/cps2_objects.py funnel` gives
commands per frame, off-screen and empty tiles, row runs and live banks over a golden. Plan for the worst frame,
not the mean.

## Screen fit

CPS2 is 384x224; Saturn NTSC is 320 or 352 wide. Options:
1. **Crop at 352, 1:1 (start here):** 16 px off each side, every layer at native size, HUD rows moved flush to the
   edges. It needs one name and one character read per VDP2 layer and leaves CPU access slots open. Capcom's own
   CPS2 ports on the Saturn run unscaled with all layers on.
2. **Scale:** VDP2 reduction on the scroll layers and scaled VDP1 sprites by a fixed table. It keeps the whole play
   area, but reduced layers need twice the VRAM reads and are the easiest way to break the VDP2 access-cycle rules
   on hardware (see `saturn-bringup`).
Make the crop the first console control, then decide. Keep both behind a build switch and compare in alternating
windows of the same scene. Check git history first: a fit may already exist in an older engine.

## HUD

Move HUD rows, not the whole picture: top and bottom rows go flush left and right. Keep the game's own font from
scroll 1; never redraw it. Check both normal play and every home mode's HUD. TVs crop the edges (overscan), so inset
flush HUD rows by one cell per side and confirm on a console: emulators show the last column whole.

## Display registers: one coherent write per vblank

Scroll, priority and window registers must change once per vblank, from one complete record.
- A scroll register written mid-picture restarts the layer from that line (AvP drew its HUD twice).
- A per-register latch that copies whatever is current at vblank mixes old and new pictures. In AvP's model of the
  old latch, 720 of 904 end states were mixed.
- Instead: stage the whole record, publish it with a sequence word, and at vblank apply the last complete record.
  Model-check the interleavings (`tools/latch_model.py`).
- Any screen that takes over the display (a reveal, a cutscene, a test screen) must reset the latch on entry and
  exit. One such screen came out black because the latch kept overwriting its registers.

## VDP1 command lists

Don't rewrite a command table the VDP1 may still be drawing. Double-buffer the lists, or wait for the draw-end flag
before writing. A race here shows as sprites vanishing for a picture, and only in some emulator renderers, so test
on more than one.

## Translucency and colour calculation

Use VDP2 per-dot colour calculation for menu panels and shadow effects. VDP1 half-transparency is costly and
interacts with priorities; test it on the busiest scene.

## Drawing on the slave SH-2

Master runs game logic and copies a per-frame snapshot at vblank. Slave owns VDP1, VDP2, CRAM, caches and shadows
and draws from the snapshot. One handoff per frame; a busy slave skips a picture, never the game. VDP1 has no erase
in manual mode: put a clear polygon at the head of each list or old pixels trail.

## Memory: cart pages and round files

Budgets are separate: work RAM high (1 MB) and low (1 MB), VDP1 VRAM (512 KB), VDP2 VRAM (512 KB), SCSP RAM
(512 KB), and the 4 MB cart. Keep a map of each.

- **Census first.** Record which ROM pages and tile keys each stage reads, from many MAME routes: every
  character, KO and continue paths, attract, and every home mode. One route is never enough. Add a button-fuzz
  census too: AvP's random play looked up 8-10% more sprite keys than all its routes, and the gap didn't close.
- **Story and cut-in pictures** need their tiles in the stage file that shows them. Census the story pages too.
- **Script reads from tile pages:** if the game reads data from a ROM page and a stage file spills tiles onto it, the
  game reads tiles as data and crashes. Trap such reads on host.
- **Shared pages.** A page read by most stages (for AvP, 10 or more) stays in every stage file. A mode or setting
  outside the census can read common tables a stage walk never touched.
- **ROM pages shared between stages.** When a file overwrites a ROM page with tiles, every stage that reads that
  page must restore it. Track a written set and restore lists per file.
- **Drop ranking.** When a stage's tiles do not fit, drop the lowest-ranked keys first. Rank by use: keys seen in
  the real full route score highest, KO/continue keys next, walk-only keys lowest. Report dropped counts per file.
- `tools/page_plan.py` computes shared pages, per-file keep sets and ranked drops from census JSON.
- Load only at stage boundaries, with the display blanked and NOW LOADING shown. Nothing loads mid-stage, and no
  data seeks while CDDA plays unless measured safe.

## Traps

- **Kept round files go stale.** A test switch that keeps last build's round files (to save build time) breaks the
  moment code layout moves: cold code or tile spills overwrite each other and show as wrong tiles or fatals. Use it
  only for kernel-only rebuilds, check the layout ends match, and never ship from a kept build.
- Whole-block allocators: pack related phase assets into one aligned block, 4-byte align embedded offsets.
- Regions round to blocks (a 4 KB cart step is 32 tiles). Report the margin to the next step, not just bytes.
- Garbled tiles that appear after a loader or packer change are often data corruption, not drawing. Check the
  files against their sources before touching the renderer (see `saturn-packaging`).
- Missing tiles draw blank. Keep a missing-key counter in the runtime and report it with every run.
- A garbled frame may be the game's own effect. Compare a MAME still of the same moment before fixing.

## Code in the kit

`saturn/gfx/` has the reusable drawing pieces: the tile slot cache (`sat_tilecache`), the VDP1 plot and frame change protocol (`sat_vdp1`), the VDP2 register latch and layout writer (`sat_vdp2`), the cycle patterns that pass `tools/vdp2_cycle_check.py` (`sat_vdp2_cycles.h`) and the unchanged-layer memo (`sat_layer`). `saturn/README.md` says what a game supplies.
