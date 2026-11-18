# Notice

## Preservation statement

This kit is intended for software preservation efforts: keeping arcade games studied, documented and playable on
period hardware. It records methods, tools and checks. It does not carry any game.

## What is not here

- No ROMs, BIOS images, encryption keys or decrypted code.
- No game data: no extracted graphics, tiles, palettes, sounds, music, text or tables.
- No generated assets, captures, memory dumps, save states, screenshots of game screens or cover art.
- No disc images (`.iso`, `.bin`, `.cue`, `.chd`) or packages built from a game.

Tools read your local files and write their output to folders you choose. Keep that output out of version control.
The `.gitignore` here blocks the common types, and every push is checked with `tools/hygiene_scan.py`.

## Rights

Capcom, CPS2, Sega, Saturn and every game named here belong to their owners. Naming a game (such as Alien vs.
Predator in the worked example) describes compatibility only and implies no affiliation or endorsement.

Use only source material you are authorized to use. A port built with this kit contains material derived from the
original game. Do not distribute such a build, or publish it, without the rights holder's permission and your own
legal review. This kit gives you no rights in any game.

## Licence of this repository

| Files | Licence | Why |
| --- | --- | --- |
| `saturn/**` | MIT ([LICENSE](LICENSE)) | Moved from AvP Saturn (`avpsaturn` v0.1.0-beta, and later pieces from its `release/v0.1.2-beta`) with the owner's approval; each file header names its source. No code from GPL projects. `saturn/cd/sat_lzdec.h` follows the method of `puff.c` (zlib licence), credited below. |
| `tools/**/*.py`, `tools/**/*.lua`, `tests/**` | MIT ([LICENSE](LICENSE)) | Written for the AvP Saturn project and generalised here, or written for the kit. No code copied from MAME, Yabasanshiro or any other GPL project. The CPS-1 / CPS-Dash behaviour in `tools/cps_objects.py`, `tools/cps_tiles.py` (mapper) and `tools/cps_video.py` was written from reading MAME's CPS-1 driver (`src/mame/capcom/cps1*.cpp`, BSD-3-Clause, Paul Leaman and the MAME team): the behaviour is described and re-implemented; no code and no per-game tables are copied. |
| `skills/**`, `playbook/**`, `configs/**`, top-level docs | MIT ([LICENSE](LICENSE)) | Our own writing. |

The MAME Lua scripts call MAME's documented Lua scripting API. They contain no MAME source, so they are not
derived works of MAME. The Yabasanshiro MCP harness talks to the emulator over its MCP port and window messages;
it contains no Yabasanshiro source.

Left out on purpose: the AvP patches against Yabasanshiro (pad input over MCP, raw SCSP dump, soft-core fixes) are
changes to GPL-2.0 code and would carry that licence. They are listed in `tools/NOT-PORTED.md`. If they are added
later, they go in their own folder with the GPL-2.0 text and a note, and this table is updated.

Third-party tools you install (MAME, Yabasanshiro, SH-ELF GCC, Jo Engine, SGL, capstone, numpy) keep their own
licences and are not bundled.

## Methods learned from other projects

Two projects shaped how AvP Saturn was built. We learned methods from them and wrote our own versions in our own
words. No code or text from either is copied here.

- **LORecomp** ([freefrank/LostOdysseyRecomp](https://github.com/freefrank/LostOdysseyRecomp), GPL-3.0), a static
  recompilation of Lost Odyssey. Its recompiler width and control-flow audit, generation guard, issue triage and AI
  workflow notes led to the kit's boundary convergence, semantics audit, generation receipts, the four work states
  and the player issue loop.
- **Game Decompilation Skill for Claude**
  ([lemiur/Game-Decompilation-Skill-For-Claude](https://github.com/lemiur/Game-Decompilation-Skill-For-Claude)).
  AvP's backlog drew on its case for decompiling over emulating and on its parallel-worker discipline, which fed
  the lift-then-make-readable approach.

Credit for those ideas goes to their authors. Their licences cover their own repositories, not this one.

## Decisions (owner, 2026-11-08)

The owner chose the options that avoid conflict:

- **Holder:** the copyright line stays "lamb2k and cps2saturn contributors".
- **Tool code from AvP Saturn:** the owner wrote it, so it is MIT here. AvP Saturn itself gets no open-source licence, because it holds code and data derived from the game. Only its original tooling is open, and that tooling lives here.
- **Method notes:** they are methods only, written in our own words, with no code copied, so other projects' licences do not apply to them.
- **Going public:** this repo stays private until AvP Saturn's release, and goes public with it.

## Other credits

- `saturn/cd/sat_lzdec.h` follows the canonical symbol decode of `puff.c` by Mark Adler (zlib licence, permissive). It is credited here and in the file header.
- The `saturn/` platform code was written for the AvP Saturn port by the repository owner and moved here under the MIT licence. It needs Sega's SGL headers and libraries only for `saturn/cd/sat_gfs_io.c`; those are not included.
