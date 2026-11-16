# Design: CPS-1 and CPS-Dash boards in the kit

Status: DRAFT. Rollout steps 1 (capture), 2 (objects) and 3 (tiles) are built, host-tested and checked in
MAME 0.289 on `dino` (CPS-Dash), and so is a whole-frame reference with the scroll layers (`tools/cps_video.py`).
See "Step 1 in MAME", "Steps 2 and 3 in MAME" and "Scroll layers in MAME" below. Step 4 (docs) is done. Step 5,
a real port's phase 0, is not started. CPS-2 behaviour is unchanged except for one deliberate change: the golden
runner now shuts host input out of MAME ("Step 1 in MAME").

## 1. Goal

A port of a CPS-1 or CPS-Dash game should use this kit the same way a CPS-2 port does: the same playbook, phases
and gates, the same Saturn platform code and the same tools. The board's differences live in the per-game config
and in a few board-aware tools. (CPS-Dash means the QSound CPS-1 boards, also called CPS-1.5.)

Hard constraint: CPS-2 keeps working unchanged. `configs/avspu.example.yaml` must produce the same MAME command,
the same golden bytes and the same tool output as today, and every existing test must pass unedited.

## 2. Non-goals

- Renaming the repo, the skills or the `CPS2SAT_` environment prefix. Revisit this once a CPS-1 or Dash game
  reaches phase 4 through the kit.
- CPS-3, ZN or any non-Capcom board.
- Anything that runs an emulator on the Saturn.
- Per-game values in the kit. The kit holds the shape of each config key, and the numbers come from the game's
  own work, as they do today. That includes the per-game graphics mapper and CPS-B tables: MAME's are BSD-3, but
  the kit's rule is that no MAME code or tables are copied in (see NOTICE.md).

## 3. What differs between the boards

Facts come from MAME 0.289 source (tag `mame0289`, `src/mame/capcom/`). Citations are file:line. They show what
MAME models, which is the kit's reference; they are not hardware measurements.

| | CPS-1 | CPS-Dash | CPS-2 |
| --- | --- | --- | --- |
| Games (MAME sets) | Many (sf2, ffight, captcomm, ...) | wof, dino, punisher, slammast, mbomberj, and regional sets (cps1.cpp:15142-15165) | Many (avsp, ...) |
| Main 68000 encryption | None | None | Yes, decrypted opcode view (cps2.cpp:1743) |
| `cpu.spaces["opcodes"]` in MAME Lua | nil (m68000.cpp:187, luaengine.cpp:1595) | nil | present |
| Work RAM | 0xff0000-0xffffff | same | same |
| GFX RAM (scroll maps, objects, palette source) | 0x900000-0x92ffff | same | same |
| CPS-A / CPS-B registers | 0x800100 / 0x800140 (cps1.cpp:586-589). Some sf2 revisions move CPS-B | same | 0x804100 / 0x804140, mirrored at 0x8001x0 |
| Object table | In GFX RAM. Base is CPS-A reg 0x00 × 256, aligned to 0x800, size 0x800 (cps1_v.cpp:2099-2111, 2539, 2313) | same | Fixed at 0x708000, size 0x2000, second bank at 0x700000 (cps2.cpp:1280, 793) |
| Object end marker | `attr & 0xff00 == 0xff00` (cps1_v.cpp:2704) | same | `y >= 0x8000 or attr >= 0xff00` (cps2.cpp:851) |
| Object code | 16 bits, through the per-game graphics mapper | same | 16 bits + `(y & 0x6000) << 3`, linear, no mapper |
| Per-object priority, relative flag | No and no. Draw order comes from CPS-B layer control (cps1_v.cpp:2973) | same | Priority in x bits 13-15; attr bit 7 adds the offset registers (cps2.cpp:893, 900) |
| Block code wrap in a 16-code row | All four flip cases (cps1_v.cpp:2789-2843) | same | Unflipped only (cps2.cpp:926-978) |
| Object coordinates | 9-bit, drawn raw (cps1_v.cpp:2859) | same | 10-bit, with x/y offset registers |
| Object buffering | Copied at vblank, drawn a frame late (cps1_v.cpp:3063) | same | Copied at vblank (cps2.cpp:1066) |
| Graphics ROM mapping | Per-game PAL mapper: code range per layer → bank (cps1_v.cpp:1402, 2385-2425) | same | One fixed mapper for scroll layers; sprites linear (cps1_v.cpp:1613-1622) |
| Tile format | 4bpp planar, `gfx_cps1` layout | same | Same layout after MAME unshuffles the ROMs (cps2.cpp:758-786) |
| Per-game CPS-B table | Layer control, priority masks, layer enables, palette control, ID and multiply protection (cps1.h:61-103) | Same table, QS1 to QS5 presets | Falls back to one `cps2` entry (cps1_v.cpp:2034) |
| Palette | 0xc00 pens, brightness in bits 12-15, RGB 4-4-4, base in CPS-A 0x0a | same | same |
| Visible picture | 384 × 224 (cps1.h:39-47) | same | same |
| Frame IRQ | Level 2 autovector, vector table entry 0x68 (cps1.cpp:348-416) | same | Level 2 at line 240, plus a raster IRQ on level 4 |
| Game settings | DIP switches (DSWA-C), so MAME keeps them in `cfg/` | 93C46 EEPROM, so `nvram/` (cps1.cpp:4002) | 93C46 EEPROM, so `nvram/` |
| Sound CPU | Z80, unencrypted | Z80 with Kabuki-encrypted opcodes (cps1.cpp:3993) | Z80, unencrypted in MAME |
| Sound chips | YM2151 (FM) + OKI MSM6295 (ADPCM) | QSound | QSound |
| 68000 → sound | Latches at 0x800180 (command) and 0x800188 (fade) | Shared Q RAM at 0xf18000 and 0xf1e000, low byte only | Shared Q RAM at 0x618000 |

What this means:

- **Dash is CPS-1 video with CPS-2 sound.** A Dash port reuses the existing audio method and changes only the
  capture and graphics side.
- **The Saturn side does not change.** The picture size, palette format, scroll layers and row scroll are the
  same on all three boards. `saturn/` needs nothing new. `sat_opx` is already opt-in, and CPS-1 and Dash ports
  leave it out.
- **The capture side has one real break.** `golden.lua` taps the IRQ entry on the opcode space, which does not
  exist on CPS-1 or Dash, so it should fail on its first tap. That conclusion comes from reading MAME's source;
  it has not been run.

## 4. Where the kit is board-specific today

| Piece | Today | Why it is board-specific |
| --- | --- | --- |
| `tools/mame/golden.lua` | Taps the IRQ entry on `cpu.spaces["opcodes"]` and dumps object RAM at a fixed base | Opcode space and a fixed object table are CPS-2 traits |
| `tools/mame/dump_code_spaces.lua` | Dumps the program and opcode views | Only CPS-2 has two views |
| `tools/mame_golden_run.py` | Seeds `nvram/` from a baseline | Plain CPS-1 settings are DIPs, which live in `cfg/` |
| `tools/cps2_objects.py` | Decodes CPS-2 objects and computes funnel stats | End marker, code high bits, relative flag, coordinate width, block wrap |
| `tools/cps2_tiles.py` | Planar to packed 4bpp; codes are offsets from two region bases | CPS-1 and Dash map codes to ROM through a per-game mapper |
| `tools/opx_store.py`, `saturn/rt/sat_opx.*` | Opcode view store and lookup | Only needed for an encrypted program; already opt-in |
| `skills/cps2-capture`, `skills/saturn-audio`, parts of `skills/saturn-graphics` and `playbook/PLAYBOOK.md` | Written for CPS-2 and QSound | Text only |

Nothing else has a board dependency: the rest of `saturn/`, packaging, gates, clips, video, `dis68k.py`,
`golden_reader.py`, `page_plan.py` and `sector_store.py` stay as they are.

## 5. Design

### 5.1 One board key, with defaults per board

Add `game.board` to the config, set to `cps2`, `cps1` or `cpsdash`. A config without it means `cps2`, so every
existing config keeps working.

A new `tools/boards.py` holds what is fixed per board. Step 1 needs only whether there is an opcode space, how
the object table is found, its size and alignment, and the CPS-A and GFX RAM addresses. Later steps add keys
when they need them, such as the object format and the sound family. It holds facts from the table above, not
MAME code. Each tool asks `boards.py` for a value, and the
config can override any of them: some sf2 revisions move CPS-B, for example.

```yaml
game:
  board: cpsdash               # cps2 (the default when missing) | cps1 | cpsdash
video:
  cps_a: 0x800100              # board default; override only for sets that move it
  cps_b: 0x800140
ram:
  object_table: register       # cps1/cpsdash: follow the CPS-A object base. cps2: object_base/object_size as today
  object_size: 0x800
paths:
  cfg_baseline: "${CPS2SAT_CFG_BASELINE}"   # cps1: DIP settings (MAME cfg folder). cps2/cpsdash use nvram_baseline
graphics:
  mapper:                      # cps1/cpsdash: the game's code ranges per layer, filled from your own work
    bank_sizes: [0x0, 0x0, 0x0, 0x0]
    ranges: []                 # [layer, first code, last code, bank]
```

### 5.2 Capture (`golden.lua`, `mame_golden_run.py`, `dump_code_spaces.lua`)

- **IRQ tap.** `golden.lua` uses `cpu.spaces["opcodes"] or cpu.spaces["program"]`. On CPS-2 nothing changes.
  On CPS-1 and Dash, opcode fetches go through the program space, so the same tap and the same prefetch check
  still work. The IRQ level (2) and the vector check are already per-game config.
- **Object table.** When the runner sets `CPS2SAT_OBJ_REG` (the CPS-A object base register and the alignment),
  `golden.lua` puts a write tap on that register. It keeps the current base, computed as MAME does
  (`0x900000 + ((value × 256) & ~(align − 1) & 0x3ffff)`), and dumps `object_size` bytes from there in the
  record's object slot.
- **Record format is unchanged.** The object slot is 0x800 bytes instead of 0x2000, and the size already comes
  from the config. Base changes go to a new sidecar, `golden.bin.obj.txt` (`irq base` lines), so readers that
  parse `golden.bin` or `golden.bin.io.txt` are unaffected.
- **Settings baseline.** The runner copies `paths.cfg_baseline` into the run's `cfg/` folder, the same way it
  copies `nvram_baseline` into `nvram/` today.
- **Code dumps.** `dump_code_spaces.lua` writes only the program view when there is no opcode space, and says so
  on stdout. For CPS-1 and Dash, the merged image the lifter needs is simply the program dump.

### 5.3 Objects (`tools/cps_objects.py`)

`cps2_objects.py` becomes `cps_objects.py`, which has one decoder per object format:

| | `cps2` | `cps1` (CPS-1 and Dash) |
| --- | --- | --- |
| End marker | y ≥ 0x8000 or attr ≥ 0xff00 | attr & 0xff00 = 0xff00 |
| Code | + (y & 0x6000) << 3 | 16 bits; mapped later by the tile packer |
| Coordinates | 10-bit, relative flag, offset registers | 9-bit, raw, minus the visible window origin (64, 16) |
| Block wrap | Unflipped only | All flips |
| Priority | x bits 13-15, kept on the tile | None; the layer order comes from CPS-B |

`decode` and `funnel` keep their output, and the board comes from the config. `cps2_objects.py` stays as a
two-line entry point for `cps2`, so existing scripts and `test_cps2_objects.py` do not change.

### 5.4 Tiles (`tools/cps_tiles.py`)

The planar-to-packed conversion, pen remap, dedupe and SGP1 format are shared by all three boards. The new part
is a mapper step that runs before the payload read. It follows MAME's `gfxrom_bank_mapper`: shift the code by
the layer's amount (sprites 1, scroll1 0, scroll2 1, scroll3 3), find its range in `graphics.mapper.ranges`, and
add the sizes of the banks before it. A code with no range counts as missing, the same as a blank tile. With no
mapper in the config, the tool behaves exactly as `cps2_tiles.py` does today, and `cps2_tiles.py` stays as an
entry point.

The kit does not say how the `GFX_REGION` input file is made. The packer reads the `gfx_cps1` planar layout, so
CPS-2 bytes have to be in MAME's decoded order (after `cps2_gfx_decode`). CPS-1 and Dash ROMs need no unshuffle.
The tools README should say this for all three boards.

### 5.5 Audio

There is no kit code in this step, only skill text.

- **Dash:** QSound, the same as CPS-2. The existing `saturn-audio` method holds. One difference: the Z80 sound
  driver is Kabuki-encrypted, so read its command table from MAME's decrypted Z80 opcode space.
- **Plain CPS-1:** music still goes to CDDA, rendered from MAME. Effects come from two sources:
  - OKI6295 ADPCM samples, decoded to PCM, become SCSP clips. This is simpler than QSound.
  - Effects made on the YM2151 are recorded from MAME per command, as clips.

  Hook the command path at the 0x800180 latch. An OKI sample extractor is a likely later tool. It is not part of
  this design.

### 5.6 Skills and playbook

The skill names stay the same. Changes:

- `cps2-capture`: add a "Board notes" section covering the opcode space, the object-base register, DIPs versus
  EEPROM, and the graphics mapper.
- `saturn-graphics`: CPS-1 has no per-sprite priority, and the layer order comes from CPS-B layer control (two
  bits per layer).
- `saturn-audio`: add the CPS-1 FM + ADPCM path and the Dash Kabuki note.
- `cps2-saturn-port`: one line saying the workflow covers all three boards, with a pointer to the board notes.
- Playbook phase 0 and the new-game checklist: set `game.board`; find the object base register writes; fill the
  mapper; record DIP settings for CPS-1.
- `configs/cps1.example.yaml`: the shape only, with every value marked FILL like the `capture:` section. A real
  worked example waits for a real port.

## 6. Tests

- Every existing test passes unedited. That is the regression gate for CPS-2.
- One new smoke test per new code path, on synthetic data, as today:
  - a CPS-1 object list through the CPS-1 decoder, including flipped-block wrap and the end marker;
  - a mapper table through the tile packer, including a code with no range;
  - a CPS-1 config through `mame_golden_run.py --dry-run`, checking that `CPS2SAT_OBJ_REG` is set and the cfg
    baseline is used;
  - the existing Lua name check, extended to `CPS2SAT_OBJ_REG`.
- A test that a config without `game.board` gives byte-identical dry-run output to one with `board: cps2`.
- None of these need a ROM or MAME. Running `golden.lua` on a real CPS-1 or Dash set is the first port's phase 0
  gate, not a kit test.

## 7. Rollout

Each step is one reviewable change, and none of them touches CPS-2 behaviour.

1. **Capture (done):** the board key, `tools/boards.py`, the `golden.lua` opcode fallback and object-base tap,
   `cfg_baseline`, and program-only code dumps. Tests. This unblocks phase 0 on a CPS-1 or Dash game.
2. **Objects (done):** `cps_objects.py` with the CPS-1 format; `cps2_objects.py` as an entry point. Tests.
3. **Tiles (done):** the mapper step in `cps_tiles.py`; `cps2_tiles.py` as an entry point. Tests.
4. **Docs (done):** the skill and playbook changes, `configs/cps1.example.yaml`, and the README and tools README tables.
5. **Proof:** phase 0 of a first real Dash or CPS-1 port, using the kit unchanged. Anything it finds feeds back
   here before the kit claims support.

## 8. Open questions

1. **Which game first?** The suggestion is a Dash beat-'em-up (Cadillacs and Dinosaurs or The Punisher). The audio
   method carries over from CPS-2 unchanged, and the genre matches AvP, so most of the playbook's lessons apply
   directly. A plain CPS-1 game means proving the FM + ADPCM audio path at the same time as the video changes.
2. **When to sample the object base.** If a game flips the base between two tables, the host check has to agree
   with MAME on which one counts at each IRQ. `dino` does flip, every frame. At every IRQ entry the base the kit
   tracked matched MAME's own register, and every table it dumped was complete. Still unchecked: whether MAME's
   vblank copy reads the same table the kit dumps. A game that writes the register late in the frame could split
   them.
3. **Scroll maps and video registers are not in the golden on any board today.** The host check compares work
   RAM and objects only. Adding GFX RAM would help all three boards, but the delta format indexes words with a
   u16. 64 KB of work RAM plus 192 KB of GFX RAM is exactly 65536 words, so there is no room for the object
   slot. That needs a format version, so it is left out of this design.
4. **Where the 68000 writes sound commands in Q RAM** (Dash and CPS-2). MAME only maps the shared RAM. Find it
   per game, as AvP did.
5. **The CPS-2 flipped-block wrap.** MAME's own comment marks the unflipped wrap as a game-specific fix, so the
   CPS-2 behaviour may be incomplete emulation. It does not affect CPS-1, but `cps_objects.py` copies it for CPS-2.

## Step 1 in MAME

MAME 0.289 tier, on Cadillacs and Dinosaurs (`dino`, World 930201, CPS-Dash), attract mode, 1200 frames, no
route.

The set did not audit clean. Every program, graphics and sound ROM matched, but six PAL logic dumps were missing
or the wrong length (`cd63b.1a`, `d7l1.7l`, `d8l1.8l`, `d9k2.9k`, `d10f1.10f`, `ioc1.ic1`). They ran from
zero-filled stand-ins, which MAME accepts with a checksum warning. MAME does not use PAL dumps to emulate the
game, but a port's phase 0 gate still needs a clean audit.

| Check | Result |
| --- | --- |
| `dump_code_spaces.lua` | Printed `NO_OPCODE_SPACE`, wrote the 2 MB program view. Level 2 vector (0x68) points at 0x542 |
| `golden.lua` IRQ tap on the program space | 1127 records in 1200 frames, each 72 + 0x10000 + 0x800 bytes |
| Object base tap | First write at IRQ 251. After that the base flips between 0x900000 and 0x904000 on every IRQ (double buffering) |
| Tracked base against MAME's own `:cps_a_regs` share, read at each IRQ in a separate run | 876 of 876 match |
| Dumped tables | Every table from IRQ 251 on has an end marker (up to 19 entries), except IRQs 849 and 850, where both buffers are all zero (a screen clear in attract) |
| `golden_reader.py` without `ram.object_size` | Reads the records at the board's 0x800 |
| Repeatability | Two runs are byte-identical, and a delta golden decodes to the same 1127 records as the full one. That holds only after the runner fix below |

That run found one kit bug, which affects every board. The runner did not shut host input out of MAME: keys held
on the Mac reached the game (one run read 0xffef at 0x800000, P1 button 1, where another read 0xffff), so two
runs of the same route differed. `mame_golden_run.py` now passes `-keyboardprovider none -mouseprovider none
-joystickprovider none -lightgunprovider none`. This changes the CPS-2 command line too, on purpose.

## Steps 2 and 3 in MAME

`tools/sprite_check.py` (now `tools/video_check.py --off scrolls`) is the acceptance check for steps 2 and 3. MAME draws the sprite layer on its own: the
scroll layers are switched off by clearing their enable bits (0x16 on dino) in every write the game makes to the
CPS-B layer control register. The kit then draws the same frame itself:
- the object table comes from the golden's record (step 1's capture);
- the decode is `cps_objects.py`'s CPS-1 format, with the game's `graphics.mapper` applied to the base code;
- tiles come from MAME's graphics region, drawn with the first entry on top.

The two pictures are compared pixel for pixel. Colours come from MAME's palette, so the check covers geometry,
tiles, ordering and the captured table, not palette conversion.

Same set, same stand-ins and same audit caveat as step 1. The run was the attract gameplay demo: 102 frames between
frames 3600 and 4590, including 12 consecutive ones.

| Check | Result |
| --- | --- |
| Record offset (`--search`) | Offset 1 matches all 102 frames with 0 differing pixels. Offsets 0, 2 and 3 fail 98 or 99 of the 102. Offset 1 is MAME's one-frame sprite delay |
| Gate at offset 1 | 102 of 102 frames, 0 pixels differ |
| What the frames hold | 11854 on-screen tiles, 2601 multi-tile blocks, 6416 x-flipped and 62 y-flipped tiles, 14 palette banks |
| Flips ignored (deliberate break) | 0 of 102 pass |
| Picture origin 1 px off (deliberate break) | 0 of 102 pass |
| Wrong palette bank (deliberate break) | 0 of 102 pass |
| Last entry drawn on top (deliberate break) | 0 of 102 pass |
| No 16-code row wrap (deliberate break) | 102 of 102 still pass: no block in these frames crosses a 16-code row |

Not proven in MAME yet:
- **The row wrap**, which none of these frames exercise. It is covered only by `tests/test_cps_objects.py`.
- **A mapper that actually maps.** dino's mapper is the identity, so the mapper is covered only by unit tests.
- **Scroll-layer tiles** (scroll1 to scroll3 through the mapper), which this check does not draw.
- **Plain CPS-1.**

A plain CPS-1 game with a non-identity mapper (for example `ffight` or `captcomm`) and some frames with wrapping
blocks would close the first two gaps.

Known edge, by design: `cps_tiles.py` maps each key on its own, while the sprite hardware maps a block's base code
and then steps through the row (`cps_objects.py` does the same as the hardware). A block that crosses a mapper
range edge can therefore differ between the two. The Saturn side should map the base code first, as the hardware
does.

## Scroll layers in MAME

`tools/cps_video.py` draws a whole CPS-1 / CPS-Dash frame as MAME draws it:
- the three scroll maps: map layout, 14-bit scroll3 codes, flips, scroll1's alternating 8-pixel halves, scroll and
  row scroll;
- sprites;
- the CPS-B layer order;
- the priority masks, under which some pens of the layer just below the sprites cover them.

It is the reference the Saturn side has to reproduce, and `tools/video_check.py` compares it with MAME's picture.
The comparison uses GFX RAM and the CPS-A/CPS-B registers, captured beside the golden. The registers are
write-only on the bus, so the capture reads MAME's own copies of them. Colours come from MAME's palette.

Same set, stand-ins and audit caveat as before. Attract gameplay demo, `dino.yaml` with MAME's CPS_B_21_QS2 values:
layer control at CPS-B + 0x0a, priority registers at 0x0c, 0x0e, 0x00 and 0x02, and enable masks 0x16 for all
three layers.

| Check | Result |
| --- | --- |
| Whole picture, 102 frames (3600 to 4590, with a run of 12 consecutive frames) | Offset 1: 102 of 102, 0 pixels differ. Offsets 0, 2 and 3 pass 4 of 102 |
| Sprites only (`--off scrolls`), 50 frames | 50 of 50, 0 pixels differ |
| Scroll2 off, scroll3 off, and both off, 50 frames each | 50 of 50 each, 0 pixels differ |
| Scroll1 off alone | Refused: on dino its enable mask is shared with the other two layers |
| Priority masks ignored (deliberate break, 34 frames) | 0 of 34 pass |
| Layer order reversed, or a fixed s1-s2-s3-sprites order (deliberate breaks) | 0 of 34 pass |
| Picture origin y off by 1, or scroll2 read with scroll1's map layout (deliberate breaks) | 0 of 34 pass |
| Scroll-tile flips ignored (deliberate break) | 33 of 34 still pass: only one frame has a flipped scroll tile in view |
| Scroll1 always the left half (deliberate break) | 34 of 34 still pass: not exercised |

The first capture read GFX RAM and the registers at the end of the same frame as the picture. Every frame where
the camera moved failed: the layers looked right but sat a few pixels out. Reading the state at the end of the
frame before matched every frame. So the picture `screen:pixels()` returns at the end of a frame was drawn from
the state one frame earlier, and `mame/video_frames.lua` now saves the state a frame early. Static frames passed
both ways, so a still screen cannot catch a timing error like this one.

What dino exercises in these frames: one layer order (scroll3, scroll2, sprites, scroll1 from the bottom), the
priority registers 0x0, 0xfe, 0x7ffe and 0x7f00, and all four priority groups on scroll2.

Not exercised, so not proven in MAME:
- row scroll (video control bit 0 is never set);
- scroll1's half selection;
- scroll-tile flips beyond one frame;
- other layer orders;
- a mapper that actually maps;
- scroll3 codes of 0x4000 and up;
- stars and flip screen, which `cps_video.py` does not draw.

The gameplay a route reaches, and a plain CPS-1 game, would cover more. `video_check.py` already captures any
frames a route reaches.

This also answers part of open question 3: the video check carries GFX RAM and the registers beside the golden,
per captured frame, so the golden format did not need to change for this.
