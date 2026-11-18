# saturn/: game-neutral Saturn platform code

C and SH-2 assembly for the parts of a native Saturn port that do not depend on the game. Two ports use the same ideas, so the code lives once, here.
It was written for the AvP Saturn port, ran on a console there, and was moved into the kit with the owner's approval under the kit's MIT licence.
The file headers name the AvP file each piece came from (`avpsaturn v0.1.0-beta`).

No ROM bytes, game data or derived assets are here. Every address and size a game needs is a parameter (`include/sat_cfg.h`) or a table the game
supplies. AvP-specific names, stage tables, addresses and character logic stayed in AvP.

## State and what the tests mean

| Tier | What it shows | Where |
| --- | --- | --- |
| HOST | The pure logic behaves: scenario tests in C driven from Python, with the chips replaced by arrays or logging callbacks | `tests/test_saturn_host.py`, `tests/c/` |
| BUILD | Every module compiles for the SH-2, warnings as errors | `tools/saturn_build_check.py` |
| EMULATOR, CONSOLE | Not claimed here. The code ran as part of the AvP port. Re-proving it in a port that adopts the kit is that port's job | |

Run `python -m unittest discover -s tests` for everything. The host C tests need `cc`, `gcc` or `clang`; the build check needs your own SH-2
toolchain (see "Building"). Without them those tests are skipped, and a skip is not a pass.

## Modules

Each row: what it is, its interface, and what a game must supply.

### include (`include/`)

| File | What it is |
| --- | --- |
| `include/sat_hw.h` | Register and memory map addresses every module shares (SCU, SMPC, VDP1, VDP2, SCSP, CD block, SH-2 timer and cache) and the cache-through alias helpers. `-DSAT_HOST` turns the alias into the identity for host tests |
| `include/sat_cfg.h` | Every address and size a game chooses, as a macro with a default. A game names its own header with `-DSAT_GAME_CFG='"mygame_cfg.h"'` and that is included first |

### boot (`boot/`)

| Module | Interface | A game supplies |
| --- | --- | --- |
| `boot/crt0.S` | Entry of the loader image: interrupts off, stack, bss clear, `sat_boot_main()` | Nothing. Link it first (`ld/boot.ld.in`). A loader that keeps SGL's own start code skips it |
| `boot/sat_diag.c`, `sat_diag.h` | Boot display on VDP2's back screen: a band per step, a progress tick, 16 bit stripes, a red or magenta flash on failure. `sat_diag_init/stage/tick/info/fail`, exception stubs, a six word call table (`SAT_DIAG_API_ADDR`) the runtime uses until its own first picture | The 512 VDP2 VRAM bytes at `SAT_DIAG_TAB_ADDR` kept clear; optionally `sat_diag_restore` to put back registers it changed |
| `boot/sat_boot.c`, `sat_boot.h` | `sat_boot_clock_change()` (BIOS service for the 352 wide mode, then VDP2 registers zeroed as SGL does), `sat_boot_cart_enable()` (4 MB cart on the BIOS timing, then a faster timing that has to pass the soak test, with fallback to the BIOS timing, a SAROO left on its own timing, and coded failures), `sat_boot_enter()` | The faster A-bus timing words if the defaults do not suit (`SAT_CART_OURS_*`); `SAT_CART_BIOS_TIMING` to never try the faster one |
| `boot/sat_cart_soak.c`, `sat_cart_soak.h` | The cart timing soak test: `sat_soak_run()` (pure, runs on a PC) and `sat_boot_cart_soak()` (the cart at `SAT_CART_SOAK_BASE`, then a cache purge) | `SAT_CART_SOAK_BASE`: a cart area nothing has been loaded into yet |
| `boot/sat_boot_main.c`, `sat_boot_main.h` | The loader's `main()`: diagnostics, clock, cart, GFS, each listed file to its address, publish the region loader, enter the runtime | `sat_boot_files[]` (name, address, failure code) and `sat_boot_file_count`; optionally `sat_boot_before_enter()` |
| `ld/boot.ld.in`, `ld/rt.ld.in`, `ld/README.md` | Link script templates with `@NAME@` holes: loader, and runtime with high work RAM, low work RAM and cart sections | The object lists and base addresses |

### cd (`cd/`)

| Module | Interface | A game supplies |
| --- | --- | --- |
| `cd/sat_store.c`, `sat_store.h` | Round files read from one shared sector store (`tools/sector_store.py`): `sat_store_open/select/read`, `sat_store_load_round` runs a round's regions to their addresses with a mark callback and a hook for special regions. Pure C: four IO callbacks | The IO callbacks (or `sat_gfs_io.c`), a 512 word head buffer, the mark and special hooks if it uses them |
| `cd/sat_gfs_io.c`, `sat_gfs_io.h` | Binds the loader to Sega's GFS: `sat_gfs_init`, `sat_gfs_load_file` (chunked, ticks the boot display), `sat_gfs_load_regions` (the call the runtime makes between rounds) | Sega's `SEGA_GFS.H` and libraries from your own SDK copy (not in the kit) |
| `cd/sat_lzdec.h` | Raw deflate decoder with no libc, decoding streams in place at the end of the destination while they arrive (`lz_unit`, `lz_unit_step`) | The compressed layout (streams padded to sectors, the tail kept in scratch). The AvP packer that wrote it stayed behind |

### rt (`rt/`)

| Module | Interface | A game supplies |
| --- | --- | --- |
| `rt/sat_ctx.S` | `_sat_start`, `_sat_slave_entry`, `_sat_switch` (coroutine switch), `_sat_vblank_entry` (saves registers, own IRQ stack, calls `sat_vblank`), exception stubs. `-DSAT_R14_SYMBOL=_name` keeps a global state pointer in r14 | C functions `sat_main`, `sat_slave_main`, `sat_vblank`, `sat_exception` |
| `rt/sat_sync.c`, `sat_sync.h` | Master and slave hand-off: the handed and done counters, wake through the FRT input capture, `sat_sync_try_handoff(begin, layers)`, `sat_sync_slave_loop(draw)`, slave start by SMPC SSHON, SCU mask re-arm in `sat_sync_vblank_begin()`, vector install | The snapshot functions (`begin`, `layers`) and the draw function; stack sizes in `sat_cfg.h` |
| `rt/sat_pad.c`, `sat_pad.h` | SMPC pad read, never blocking, one INTBACK per vblank with SF set before the command, a break for queued data, ports 1 and 2; `sat_pad_map()` | A `SatPadMap` table to its own input latch, and `sat_pad_tick()` first thing in each vblank |
| `rt/sat_opx.c`, `sat_opx.h` | CPS2 opcode view: flat accessors and a range store lookup (`sat_opx8/16/32`) falling back to the data view | The store (build it with `tools/opx_store.py` from your own files) and the data view image |
| `rt/sat_readout.c`, `sat_readout.h` | The console readout, text only: PIC, DONE, MISS, SKIP, HELD, FLIP/VBL, TICK (the game's own tick byte per 60 vblanks, no tick lost to the byte's wrap), PROF (master time shares) and the `HW SND n OK TEST t` power-up line, from counters in and changed cells out (`sat_ro_init/vblank/update/paint`); `sat_ro_chip_selftest()` reads back CRAM and both VRAMs. A release build compiles it out | The counters (`SatVdp1.shown` and `.waits`, the game's missed frames and skipped snapshots), the tick byte's address and a build id string in `SatReadoutCfg`, the cell callback that draws a character in your font, and a switch that keeps it out of release builds |

### gfx (`gfx/`)

| Module | Interface | A game supplies |
| --- | --- | --- |
| `gfx/sat_tilecache.c`, `sat_tilecache.h` | Slot cache over VDP1 texture or VDP2 cell VRAM: hash chains, clock hand that never evicts a tile the current picture uses, protection of the plot still in flight, two entry memo, negative cache for blank and missing tiles, refusal counters | Memory for the records, a `fetch` hook (payload, blank or missing for a key), an `upload` copy, slot size and count |
| `gfx/sat_vdp1.c`, `sat_vdp1.h` | Command list double buffer with a frame change that is never asked for while a list is plotting: `sat_v1_wait_end`, `sat_v1_plot` (slave), `sat_v1_vblank` (master), timeouts that recover from a replaced chip state; `sat_v1_clear` writes the full-picture clear polygon a list needs first when it does not cover the screen (the manual change mode does not erase the draw buffer on Yabasanshiro) | The command writer (`sat_v1_cmd()` gives the base of the table being built), screen size, table offsets, the slave's timer |
| `gfx/sat_vdp2.c`, `sat_vdp2.h` | Register latch (slave records and publishes whole pictures, master applies the last complete one at V-blank IN, with a sequence word and a re-check), `SatVdp2Layout` writer, back screen, VRAM clear, `sat_shadow_write32()` (write a name word only when it changed) | The register values, and which registers its draw writes |
| `gfx/sat_vdp2_cycles.h`, `vdp2_layout.example.json` | Two access cycle patterns (half reduction on NBG0 and NBG1, and none) that pass `tools/vdp2_cycle_check.py`, and the spec they are checked against | A pattern for its own layer set, checked with the tool |
| `gfx/sat_layer.c`, `sat_layer.h` | Unchanged-layer memo: sum the visible name words on the master, copy only when the sum moved (optionally flagging changed rows), and the slave redraws only when the sum differs from the last one drawn | The map pointer, window and layout (`row_bits`) |

### audio (`audio/`)

| Module | Interface | A game supplies |
| --- | --- | --- |
| `audio/sat_scsp.c`, `sat_scsp.h` | SCSP driver core with the 68000 parked: bounded SMPC sound on and off with retry, sample RAM writes, one clip on one slot (PCM 8 or 16, loop, level, pan, rate), key off, `sat_scsp_rate_word(hz)`, `sat_scsp_pan()` | The clip table and the policy: which slot, priorities, what a game command means |
| `audio/sat_cdda.c`, `sat_cdda.h` | CD audio through the CD block: queued commands sent when the block is ready (CR4 last), play and pause, intro then loop chain, fades, the SCSP input level, reset after a data load | Track numbers, the intro length in CD frames, one call to `sat_cdda_frame()` per video frame |

### tools

| Tool | What it does |
| --- | --- |
| `tools/fn_heat.py` | Per function heat from a profiling emulator's dumps and a link map |
| `tools/place_plan.py` | Which functions belong in the fast RAM and where the rest go, as linker include lists |
| `tools/opx_store.py` | Builds and reads the opcode range store |
| `tools/saturn_build_check.py` | Compiles every module for the SH-2 (the BUILD tier) |

## Wiring it up

Loader (first stage, IP.BIN loads it at `0x06004000`):

1. Fill `ld/boot.ld.in`, link `boot/crt0.S`, `sat_boot*`, `sat_cart_soak`, `sat_diag`, `cd/sat_gfs_io`, `cd/sat_store` and your `sat_boot_files[]` against SGL's libraries.
2. The loader shows the boot display from its first instruction, changes the clock, enables the cart, loads your files and jumps to `SAT_BOOT_ENTRY`.

Runtime:

1. `sat_main()` sets up memory, loads the first round through the loader's published function (`*(long (**)(const char *, void (*)(void)))SAT_LOADER_API_ADDR`, called with `"R000.BIN"` and a mark callback), initialises graphics and sound,
   calls `sat_sync_slave_start()` and `sat_sync_irq_install()`, then runs the game.
2. `sat_vblank()` (master), first thing: `sat_sync_vblank_begin()`, `sat_v2l_apply()`, `sat_v1_vblank()`, `sat_pad_tick()`; then `sat_sync_try_handoff(begin, layers)` with
   your snapshot halves; then the game's own vblank body; then `sat_cdda_frame()` and your sound step.
3. `sat_slave_main()` calls `sat_sync_slave_loop(draw, &ticks)`. `draw()` runs `sat_v1_wait_end()`, `sat_tc_frame()` on its caches, builds the list with
   `sat_tc_get()`, calls `sat_v1_plot()` (on 0, `sat_tc_abandon()`; on 1, `sat_tc_commit()`), writes VDP2 registers with `sat_v2l_write()` and ends with `sat_v2l_publish()`.
4. The snapshot's layer half sets a flag the slave waits on (`sat_sync_snapshot_*`) before it reads a layer word.

Rules the code keeps, learned on a console: emulators forgive what a console does not.

- A frame change is asked for only after VDP1 reports the end of the plot.
- Display registers reach the chip at V-blank IN, from one complete picture's record.
- Every CPU-shared word is read and written through the cache-through alias.
- Wide reads need aligned addresses; `sat_layer.c` and `sat_opx.c` read bytes where alignment is not known.
- The SMPC command goes after SF is set, and a bounded wait replaces any spin on a busy flag.
- The VDP2 access cycle pattern is checked against Sega's manual before anything is burned (`tools/vdp2_cycle_check.py`).

## Building

The toolchain is not part of the kit. `tools/saturn_build_check.py` looks for `--gcc`, `$SH_ELF_GCC`, `$JO/Compiler/WINDOWS/bin/sh-elf-gcc` (a Jo Engine tree)
and `sh-elf-gcc` on `PATH`, and for Sega's headers in `--sgl-inc`, `$SGL_INC` or `$JO/Compiler/COMMON/SGL_302j/INC`. It compiles with
`-m2 -mb -O2 -ffreestanding -Wall -Wextra -Werror`. Only `cd/sat_gfs_io.c` needs Sega's headers.

A game compiles these files with its own flags and `-DSAT_GAME_CFG='"mygame_cfg.h"'` to set addresses and sizes. Link with `-lgcc` (a few modules use libgcc's division and shifts).

## Left in AvP, and why

| AvP piece | Why it stayed |
| --- | --- |
| `saturn/rt/kernel.c`, `home*.c`, `duel*.inc`, `guests.c`, `reveal.c`, `fps_hud.c`, `unlock_save.h` | Lifted-game scheduler, menus, bonus characters and the save record: AvP's game |
| `saturn/gfx/sat_gfx.c` (the rest), `sat_vdp2_cfg.h` | The SGP tile pack format, scroll layer drawing, HUD, home menu and AvP's VRAM map |
| `saturn/audio/sat_audio.c` (the rest), `build_pack.py`, `sound_table.py` | The Z80 mailbox protocol, clip table and pan sweeps of AvP's driver |
| `saturn/rt/build.py`, `place_fn*.json`, `round_cache.py`, `fixlib.py`, `check_boot_data.py` | AvP's build, and heat data that names AvP functions |
| `tools/lzstore.py`, the coalescing of tiny regions in `boot.c` | Bound to AvP's round file layout (default off or measured only there) |
| `saturn/rt/yaba_*.patch`, `saturn/audio/yaba_wav_dump.patch` | Patches against GPL code (Yabasanshiro); not for an MIT kit (see `NOTICE.md`) |
| `loader/` (the first loader), `engine-patches/` | A loader for one `GAME.BIN` of a Jo Engine build, and a patch to that engine; tied to that build |
| Hardware-erase experiment, sprite pair experiments, profiling hooks | Default off and measured only in AvP |

Credit: `cd/sat_lzdec.h` follows the canonical decode method of `puff.c` by Mark Adler (zlib licence). Nothing in the kit comes from GPL code.
