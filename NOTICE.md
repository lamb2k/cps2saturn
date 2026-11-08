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
| `tools/**/*.py`, `tools/**/*.lua`, `tests/**` | MIT ([LICENSE](LICENSE)) | Written for the AvP Saturn project and generalised here. No code copied from MAME, Yabasanshiro or any other GPL project. |
| `skills/**`, `playbook/**`, `configs/**`, top-level docs | MIT ([LICENSE](LICENSE)) | Our own writing. |

The MAME Lua scripts call MAME's documented Lua scripting API. They contain no MAME source, so they are not
derived works of MAME. The Yabasanshiro MCP harness talks to the emulator over its MCP port and window messages;
it contains no Yabasanshiro source.

Left out on purpose: the AvP patches against Yabasanshiro (pad input over MCP, raw SCSP dump, soft-core fixes) are
changes to GPL-2.0 code and would carry that licence. They are listed in `tools/NOT-PORTED.md`. If they are added
later, they go in their own folder with the GPL-2.0 text and a note, and this table is updated.

Third-party tools you install (MAME, Yabasanshiro, SH-ELF GCC, Jo Engine, SGL, capstone, numpy) keep their own
licences and are not bundled.

## Decisions (owner, 2026-11-08)

The owner chose the options that avoid conflict:

- **Holder:** the copyright line stays "lamb2k and cps2saturn contributors".
- **Tool code from AvP Saturn:** the owner wrote it, so it is MIT here. AvP Saturn itself gets no open-source licence, because it holds code and data derived from the game. Only its original tooling is open, and that tooling lives here.
- **Method notes:** they are methods only, written in our own words, with no code copied, so other projects' licences do not apply to them.
- **Going public:** this repo stays private until AvP Saturn's release, and goes public with it.
