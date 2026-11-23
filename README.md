# cps2saturn

**Intended for software preservation efforts.**

This repository holds no ROMs, no game data, no generated assets, no captures and no disc images. It is tooling and
method only. Work only from material you own or are otherwise authorized to use. See [NOTICE.md](NOTICE.md).

## What it is

A kit for porting Capcom CPS2 arcade games to native Sega Saturn code, using the 4 MB (32 Mbit) RAM cartridge.

**CPS-1 and CPS-Dash (experimental).** The capture, object, tile and video tools also handle CPS-1 and the QSound
CPS-1 boards (CPS-Dash), chosen by `game.board` in the config. They are checked against MAME on one CPS-Dash game
only, and no CPS-1 or CPS-Dash port has used them yet. What works, how it was checked and what is still open:
[docs/design/cps1-dash-boards.md](docs/design/cps1-dash-boards.md). Start from `configs/cps1.example.yaml`.

- **Playbook:** the phases, gates and staffing, from ROM identity to a release. [playbook/PLAYBOOK.md](playbook/PLAYBOOK.md)
- **Claude Code skills:** one per area, so an agent can pick up any part of the work. [skills/](skills/)
  See the skills table below.
- **Tools:** game-neutral Python and MAME Lua tools. Game constants live in a per-game config. [tools/](tools/)
- **Templates:** lane brief, hand-back, STATUS.md and release notes. [playbook/templates/](playbook/templates/)

The approach: MAME is the reference, the game's own 68000 logic is lifted to C and then made readable, and the
Saturn side (VDP1/VDP2, SCSP, CD, cart) is written natively. It is not an emulator running on the Saturn.

## Quick start

Start from the kit's `main` branch. Record the kit commit in the game's private STATUS file so a build can be reproduced. The platform code, checks and porting skills are indexed below.

1. Install the requirements below and run `python -m unittest discover -s tests -v` from the kit root. Record skipped checks and their missing dependencies.
2. Copy [the CPS2 worked example](configs/avspu.example.yaml) to a private config for your set. Replace the game's IRQ tap, object table, input bindings and stage list with values verified in your pinned MAME. Set the ROM, work and settings-baseline paths for your machine.
3. Preview the first capture with `python tools/mame_golden_run.py --config configs/<set>.yaml --name attract-a --dry-run`. Inspect the set, IRQ tap, input providers and output directory. Once these agree with your setup, run it without `--dry-run`. Repeat under a fresh name, `attract-b`, and compare the recordings with `tools/golden_reader.py diff`.
4. Follow the [new-game checklist](playbook/PLAYBOOK.md#5-new-game-setup-checklist) through the first host comparison. Start with the [porting skill](skills/cps2-saturn-port/SKILL.md). Claude Code users can install the folders under `skills/` in their project's `.claude/skills/`; other agents can read the same files in place.

| When you need to… | Start here |
| --- | --- |
| Capture the first reproducible arcade scene | [Capture tools and route format](tools/README.md), [capture skill](skills/cps2-capture/SKILL.md) |
| Bring up the first playable Saturn image | [Platform module interfaces and integration order](saturn/README.md), [bring-up skill](skills/saturn-bringup/SKILL.md) |
| Diagnose slow fights or disputed timing | [Performance skill](skills/saturn-perf/SKILL.md), [cross-port measurement lessons](playbook/PLAYBOOK.md#what-the-follow-up-checks-caught) |
| Verify a build and prepare a hardware test | [Hardware checks](tools/README.md#hardware-gates), [release skill](skills/saturn-release/SKILL.md) |

## Skills

| Skill | Use it for |
| --- | --- |
| `cps2-saturn-port` | Start here: the phases, their gates, and which skill handles what |
| `cps2-capture` | MAME goldens, routes, watchpoints, debug menus |
| `sh2-game-logic` | Lifting 68000 code to C, host checks against MAME, readable C |
| `saturn-graphics` | VDP1 sprites, VDP2 layers, screen fit, HUD, display registers, cart pages and stage files |
| `saturn-audio` | Sound effects on the SCSP, music as CD audio, sound coverage |
| `saturn-packaging` | ISO, cue, IP.BIN, disc budget, loading, web builds |
| `emulator-testing` | Emulator runs, pad-only proofs, stills, evidence labels |
| `saturn-bringup` | First boots on a real Saturn and the faults only hardware shows |
| `saturn-perf` | Getting to full speed on a console, not just on an emulator |
| `saturn-bonus-content` | Guest characters, new modes and saves without touching arcade play |
| `saturn-release` | Release disc, gates, media, notes, going public |
| `clip-capture` | Frame-exact clips and stills from the emulator |
| `video-assemble` | Cutting captured clips into a video |
| `agent-orchestration` | Running several AI agents on one port |
| `best-practices` | The checklist before landing, measuring or releasing |

## Repo map

| Path | What is there |
| --- | --- |
| `skills/` | Claude Code skills, one folder each with a `SKILL.md` |
| `playbook/PLAYBOOK.md` | The long-form workflow, gates and lessons |
| `playbook/templates/` | Lane brief, hand-back, STATUS.md, release notes |
| `saturn/` | Game-neutral Saturn platform code: boot, loader, hand-off, VDP1 and VDP2, SCSP and CD audio (see `saturn/README.md`) |
| `tools/` | Game-neutral tools (see `tools/README.md`) |
| `tools/NOT-PORTED.md` | AvP tools left behind, with reasons |
| `configs/` | Per-game config; `avspu.example.yaml` is the worked example, `cps1.example.yaml` the CPS-1 / CPS-Dash shape |
| `docs/design/` | Design notes: CPS-1 and CPS-Dash support, with its MAME results |
| `tests/` | Smoke tests, one per tool, no ROM needed |

## Requirements

- **MAME 0.289.** Pin the exact build. It is the reference for every behaviour check.
- **Yabasanshiro** with its MCP control bridge (a debug build that serves memory reads, screenshots and pad input
  over a local MCP port). Used for emulator-tier checks of the Saturn image.
- **Saturn SH-2 toolchain:** SH-ELF GCC (9.x is known good) and a Saturn library such as Jo Engine or SGL.
  You supply SGL yourself; it is not open source and is not included.
- **Python 3.10 or newer.** Optional: `numpy` (audio compare), `capstone` (68000 disassembly), `PyYAML`
  (configs; a small built-in reader covers the example format without it).
- A host C compiler (GCC or Clang) for host-side differential tests of lifted code.

## Worked example

[AvP Saturn (lamb2k/avpsaturn)](https://github.com/lamb2k/avpsaturn) ports Alien vs. Predator (`avspu`) with this
method: lifted 68000 game to C, whole-game host check against MAME to the ending, per-stage round files from CD,
a shared sector store, home modes (duel, boss rush, stage select), a bonus character, console bring-up and a
public beta. The playbook's "Lessons from AvP" section collects what it taught.

## Credits

The method owes a lot to two other projects:
[LORecomp](https://github.com/freefrank/LostOdysseyRecomp) (Lost Odyssey static recompilation) and the
[Game Decompilation Skill for Claude](https://github.com/lemiur/Game-Decompilation-Skill-For-Claude). We took ideas,
not code. See [NOTICE.md](NOTICE.md).

## Licence

Our own tools and docs are MIT. Nothing here is copied from GPL code. Details and open questions are in
[NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).
