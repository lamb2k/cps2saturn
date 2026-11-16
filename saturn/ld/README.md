# Link script templates

Two templates, both plain text with `@NAME@` holes. A build fills them with `sed` or a few lines of Python. No game address lives here.

## boot.ld.in (the loader, first stage)

| Hole | Meaning | AvP value |
| --- | --- | --- |
| `@LOADER_BASE@` | Where IP.BIN puts the loader and jumps | `0x06004000` |
| `@LOADER_STACK@` | Bytes reserved for the loader's stack (at least 2048) | 4096 |

The loader must fit between its base and the runtime entry (`SAT_BOOT_ENTRY`, default `0x06014000`), with the diagnostic mailboxes
(`SAT_DIAG_API_ADDR`, `SAT_LOADER_DIAG_ADDR`, `SAT_LOADER_API_ADDR`, all just below the entry) clear.

## rt.ld.in (the runtime)

| Hole | Meaning | AvP value |
| --- | --- | --- |
| `@HW_BASE@` | High work RAM start for runtime code | `0x06014000` (the loader's entry) |
| `@HW_OBJECTS@` | Object files and sections that must be fast, one `*name.o(.text .rodata)` pattern per line. `sat_ctx.o` is placed first by the template so `_sat_start` sits at `@HW_BASE@` | the hot runtime and the hottest lifted code |
| `@LW_BASE@` | Low work RAM start | `0x00200000` plus what the game reserves below |
| `@LW_OBJECTS@` | Code and data that can live in the slower RAM | the rest of the lifted code |
| `@CART_BASE@` | Cart window start for cold code | the tail of the 4 MB cart |
| `@CART_OBJECTS@` | Cold code and tables | one-time and load-time code |

Sections the modules use, by name, so a game can steer one function or table without editing the module:
`.hw.text`, `.hwdata`, `.hwbss`, `.hwstack`, `.lw.text`, `.lwdata`, `.lwbss`, `.cartcode`, `.cartdata`.
`tools/place_plan.py` fills the object lists from a measured heat file. Build with `-ffunction-sections` for function level placement.

Rules the templates keep: bss is `NOLOAD` and cleared by the entry code, `.eh_frame` is dropped, and the 4 MB cart is used through its
cached window only for data the CPU reads (the cart bus is slow, so hot code never lives there).
