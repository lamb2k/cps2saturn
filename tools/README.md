# Tools

Game-neutral tools. Game constants come from `configs/<set>.yaml` (`--config`). None of them contains game
data. Their outputs are derived from your game: write them outside git.

Run the smoke tests with `python -m unittest discover -s tests -v`. They use synthetic data only.

| Tool | Area | What it does |
| --- | --- | --- |
| `cfg.py` | all | Loads the per-game config (PyYAML or a built-in reader), expands `${ENV}` values |
| `hygiene_scan.py` | repo | Pre-push scan: blocked file types, size, binary content, private paths, tokens, keys |
| `mame/golden.lua` | capture | Golden run: per-IRQ registers + work RAM + object RAM (full or delta), I/O log, route playback, state saves |
| `mame_golden_run.py` | capture | Runs MAME with `golden.lua` from the config; `--dry-run` prints the command |
| `golden_reader.py` | capture, host check | Reads full or delta goldens; shows changed words; finds the first difference between two |
| `mame/dump_code_spaces.lua` | capture | Dumps the program and decrypted opcode views over a range |
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

## Environment values the MAME scripts read

`golden.lua`: `CPS2SAT_OUT`, `CPS2SAT_IRQ_TAP`, `CPS2SAT_IRQ_VECTOR`, `CPS2SAT_WORK`, `CPS2SAT_OBJ`, `CPS2SAT_IO`,
`CPS2SAT_MAXIRQ`, `CPS2SAT_DELTA`, `CPS2SAT_ROUTE`, `CPS2SAT_ROUTE_BITS`, `CPS2SAT_LAST`, `CPS2SAT_SAVE`.
`mame_golden_run.py` sets all of them from the config.

`dump_code_spaces.lua`: `CPS2SAT_FIRST`, `CPS2SAT_LAST`, `CPS2SAT_OUT_PROGRAM`, `CPS2SAT_OUT_OPCODES`.
`dump_rom_window.lua`: `CPS2SAT_FIRST`, `CPS2SAT_LAST`, `CPS2SAT_SPACE`, `CPS2SAT_OUT`.

## Route files

One line per change: `frame word`, where bit i of the word is entry i of `inputs.route_bits`. Optional
`last N` line ends the run. Real ports only.
