---
name: cps2-saturn-port
description: End-to-end workflow and phase gates for porting a Capcom CPS2 arcade game (or, experimentally, a CPS-1 or CPS-Dash game) to native Sega Saturn code with the 4 MB RAM cart. Use when starting a new CPS2-to-Saturn port, resuming one, choosing the next phase, deciding whether a phase gate has passed, or routing work to the capture, graphics, audio, game-logic, packaging, testing or orchestration skills. For software preservation work from material you are authorized to use.
---

# CPS2 to Saturn port: the whole workflow

Build a native Saturn program from the arcade game's own logic and data. Do not ship a CPS2 emulator, do not draw
substitute sprites, and never treat a host or emulator result as hardware proof.

The project's own STATUS.md, backlog and owner instructions outrank this skill. This skill gives method and gates.

## Start or resume

1. Read the project's `docs/STATUS.md` (the one source of current state), `docs/BACKLOG.md`, the agent file
   (`AGENTS.md` / `CLAUDE.md`) and the latest hand-back. Check `git status`, branch and recent commits.
2. Check git history across branches before estimating a problem: it is often already solved somewhere.
3. Confirm the ROM set is present locally and audited (`mame -verifyroms <set>`). Never copy or commit it.
4. Find the per-game config (`configs/<set>.yaml`). Every tool reads game constants from it. Its `game.board`
   (`cps2`, `cps1`, `cpsdash`) says which board's rules the tools use; CPS-1 and CPS-Dash support is experimental,
   see `docs/design/cps1-dash-boards.md` in the kit for what is proven.

## The architecture that works

- **MAME is the reference.** A pinned MAME build gives per-frame work RAM, object RAM, palettes, inputs and audio.
- **Lift, then make readable.** Lift the 68000 program to C (one C function per recovered function, flat
  big-endian RAM at original offsets), prove it against MAME on host, then replace hot or unclear functions with
  readable C, each behaviour-gated.
- **Native platform layer.** Pads through the game's own input latch, VDP1 sprites, VDP2 scroll layers, SCSP sound
  effects, CDDA music, round files from CD, cart residency. The game logic never calls hardware directly.
- **Two CPUs.** Game logic on the master SH-2, drawing on the slave from a per-frame snapshot, one handoff per frame.

Screen capture is for evidence and regression oracles. ROM translation is for anything systematic (animation,
assemblies, hitboxes, spawns, AI). Switch to ROM translation as soon as more than a few actors are involved.

## Phases and gates

Each phase ends when its gate passes. Label every result with its tier: HOST, MAME, EMULATOR, HARDWARE.

| Phase | Work | Gate |
| --- | --- | --- |
| 0 Identity | ROM set, MAME pin, config, decrypted program and opcode views, debug features found | ROM audit clean; config filled; first golden run recorded |
| 1 First gate | Measure reachable code, lifted size and modelled cost against 2 MB work RAM + 4 MB cart | Written GO / NO-GO with numbers (MODELLED) |
| 2 Translator | Lifter, boundary convergence (0 unresolved targets or jump tables), semantics audit, generation receipts | Audit suite passes and a frozen-bad generator fails it |
| 3 Host check | Lifted game on PC against MAME goldens, per vblank, work RAM + object RAM | Clean to the end of round 1, then to the ending |
| 4 Saturn layer | Sprites, scroll layers, palettes, pad, audio, slave SH-2, memory map | Round 1 plays on the emulator with real pad input |
| 5 Fit | Round files, cart pages, drop ranking, fuzz census, loading | Whole game on the emulator image; dropped keys per stage reported |
| 6 Console | First hardware discs with on-screen diagnostics, static hardware gates, register diff, crop control | Boots and plays round 1 on a real Saturn (owner photos); faults listed |
| 7 Speed | Memory placement by heat, repeated work removed, game ticks against the arcade's rate | Busiest scene at the arcade's tick rate on the console, or the gap measured and labelled |
| 8 Home features | Title menu, options, sound test, music player, home modes, bonus content | Each feature proven by a pad-only run; normal play unchanged |
| 9 Release | Release disc without test switches, gates on it, media, notes, publish | Package hashes recorded; hardware status stated plainly |

Start console work (phase 6) as soon as round 1 plays on an emulator. Emulators hide the faults and the slowness
that only a Saturn shows, and finding them late costs the most.

Never skip a gate silently. If a gate cannot run, say so and say why.

## Which skill for which job

- MAME capture, goldens, watchpoints, debug menus: `cps2-capture`.
- Tiles, sprites, scroll layers, crop, HUD, cart pages, round files: `saturn-graphics`.
- QSound, SCSP clips, CDDA tracks, sound test, music player: `saturn-audio`.
- Lifting, readable C, host differential, parity tests: `sh2-game-logic`.
- ISO, cue, IP.BIN, CD-R budget, shared sector store, web builds: `saturn-packaging`.
- Yaba MCP runs, pad scripts, stills, evidence labels: `emulator-testing`.
- First boots on a real Saturn, hardware-only faults, VDP2 timing, register diffs: `saturn-bringup`.
- Console speed, memory placement, game-tick measurement, exactness of speed fixes: `saturn-perf`.
- Guest characters, new modes, swapped text and sound, saves: `saturn-bonus-content`.
- Release disc, gates, media, notes, going public, web build updates: `saturn-release`.
- Frame-exact clips and stills from the emulator: `clip-capture`. Cutting them into a video: `video-assemble`.
- Running several agents at once: `agent-orchestration`.
- The checklist for everything else: `best-practices`.

## Report at every checkpoint

- What is exact, what is native but approximate, what is missing.
- Host check result (golden name, dumps clean of total).
- Emulator result (image hash, route, vblanks, fatals).
- Hardware result, or UNRUN.
- The current blocker and the next command to run.

The long form is in `playbook/PLAYBOOK.md` in the cps2saturn kit.
