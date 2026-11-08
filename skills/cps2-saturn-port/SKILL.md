---
name: cps2-saturn-port
description: End-to-end workflow and phase gates for porting a Capcom CPS2 arcade game to native Sega Saturn code with the 4 MB RAM cart. Use when starting a new CPS2-to-Saturn port, resuming one, choosing the next phase, deciding whether a phase gate has passed, or routing work to the capture, graphics, audio, game-logic, packaging, testing or orchestration skills. For software preservation work from material you are authorized to use.
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
4. Find the per-game config (`configs/<set>.yaml`). Every tool reads game constants from it.

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
| 5 Fit and speed | Round files, cart pages, drop ranking, profile, readable C for hot paths | Whole game on the emulator image; frame cost measured |
| 6 Home features | Title menu, options, sound test, music player, home modes | Each feature proven by a pad-only run; normal play unchanged |
| 7 Release | ISO/cue with CDDA, disc budget, hardware test sheet, notes with stills | Package hashes recorded; hardware status stated as UNRUN until the owner runs it |

Never skip a gate silently. If a gate cannot run, say so and say why.

## Which skill for which job

- MAME capture, goldens, watchpoints, debug menus: `cps2-capture`.
- Tiles, sprites, scroll layers, crop, HUD, cart pages, round files: `saturn-graphics`.
- QSound, SCSP clips, CDDA tracks, sound test, music player: `saturn-audio`.
- Lifting, readable C, host differential, parity tests: `sh2-game-logic`.
- ISO, cue, IP.BIN, CD-R budget, shared sector store, web builds: `saturn-packaging`.
- Yaba MCP runs, pad scripts, stills, evidence labels: `emulator-testing`.
- Running several agents at once: `agent-orchestration`.
- The checklist for everything else: `best-practices`.

## Report at every checkpoint

- What is exact, what is native but approximate, what is missing.
- Host check result (golden name, dumps clean of total).
- Emulator result (image hash, route, vblanks, fatals).
- Hardware result, or UNRUN.
- The current blocker and the next command to run.

The long form is in `playbook/PLAYBOOK.md` in the cps2saturn kit.
