---
name: emulator-testing
description: Testing Saturn builds of CPS2 ports on emulators. Use for the Yabasanshiro MCP harness (memory reads, pad input, screenshots), scripted and closed-loop pad bots that use only real pad input, golden host checks, short bounded runs, stills and still pairs against MAME, one emulator instance per lane, and labelling evidence as HOST, MAME, EMULATOR or HARDWARE.
---

# Emulator testing

## Evidence tiers

Label every number and claim:
- **HOST:** lifted code on PC against a MAME golden.
- **MAME:** the arcade reference.
- **EMULATOR:** the Saturn image on Yabasanshiro (or another Saturn emulator). Emulator timers are not Saturn
  timing; write MODELLED for any frame-cost figure from them.
- **HARDWARE / CONSOLE:** a real Saturn with the 4 MB cart, usually the owner's photos of an on-screen readout.
  Only the owner can produce this. UNRUN until then.
- **MODELLED:** an emulator run with a cost model added (see `saturn-perf`). **ASSUMED:** a figure you couldn't
  find published, used in a model. Say which.
Never let a lower tier advance a higher tier's status. Record the emulator build, your patches and its settings with
every number: two copies of the same emulator with different settings give different results.

Emulators forgive misaligned accesses, VDP2 access-cycle mistakes, memory placement cost and power-up RAM contents.
A clean emulator run says little about those; see `saturn-bringup`.

## The Yaba MCP harness

A debug build of Yabasanshiro serves an MCP endpoint on a local port: memory reads and writes, screenshots and
(with a small patch) pad state. `tools/yaba_mcp.py` holds the client.

- **One instance per lane.** Each lane gets its own emulator folder with its own ini and its own MCP port. Check the
  port's owner pid before driving it: two lanes can both see a port free, start, and one bot then drives the other
  lane's machine.
- **Claim before you start.** Write a claim file in the emulator folder (lane, pid, start time) and remove it when
  done. A lane that finds another lane's live claim waits or uses its own copy. Stale claims (pid gone) may be
  taken over, with a note in the log.
- **Stop only what you started.** Record the pid when you launch. Stop that pid, or match the full command line
  including your own folder. Never stop emulators by name: the owner's window and other lanes' runs share it.
- **Back up what you replace.** Before swapping a disc image, ini, BIOS path or save file in a shared folder, copy
  the original and record its hash. Put it back after the run and check the hash matches.
- **Own window only.** Pad input goes to the emulator's own window handle (PostMessage key down/up) or through the
  MCP pad call. Never use global input (SendKeys, keybd_event, SendInput).
- Retry reads that answer empty while the core starts or during a long CD read.
- Restore the user's emulator settings after the run; edit a copy of the ini, never the user's only copy.
- Memory writes take bytes as a hex string; a list of ints may silently write nothing.
- One MCP session per emulator. A second session froze the core; add a quiet-log watchdog.
- Save states may not hold every hardware flag (AvP: the VDP1 draw-end flag). Re-check anything timing-related
  after a load.
- Each lane's patched emulator writes logs to its own folder. One lane's logger overwrote another's evidence.
- Use a fresh backup-RAM profile per run. A saved option silently changed a "default" run.
- Harnesses that scan fixed RAM ranges for a marker go stale when the memory layout changes. Take addresses from
  the ELF or the config.
- Some renderers hide faults others show (a VDP1 race showed in one video core only). Test visual fixes on two.

## A window for the owner

When the owner watches or plays a build on your PC, give them a window that works the first time: a known-good
renderer setting, its own emulator folder and ini (never a lane's), its own screen position, brought to the front,
and a capture checked to show a picture (boots can be black for a while) before you say it's ready. Lanes never
edit the owner's emulator settings.

## Pad-only proofs

A proof of play uses only real pad input through the game's own latch.
- **Scripted pad:** a fixed schedule compiled in or played by the harness. Good for repeatable smoke runs.
- **Closed-loop bot:** reads RAM over MCP (read only) and picks keys. Good for getting through a stage.
- **Memory-poke bots are diagnostics,** not proofs. If a run sets health or boss state over MCP, label it
  DIAGNOSTIC and do not count it as play. Prove the same feature again pad-only.
- Assists (invulnerability, boss health, warps) live in the harness, never in a build. Use the same bot for the
  switch-off, switch-on and baseline arms.
- Assisted or non-deterministic bot runs trigger investigations; they are not measurements.

## Short runs

Most checks should take a minute or two. Long runs drift (Yaba slowed from ~60 to ~20 vblanks/s within a minute in
some scenes; a fresh process restores speed). Join long routes as legs with save states, and say so. Bound every
run with a timeout and kill only the processes your run started.

## A/B runs and controls

- Both arms play the same scene. Key every poke and switch to the game's frame or tick counter, never to wall
  clock: emulators run at different speeds from run to run, so "after two seconds" is a different game frame each
  time. Report the evidence that both arms matched (picks, stage, the frame the fight started).
- A counter that reads differently between two runs of one image (a missing-tile count of 0 and then 370) is not a
  result for either arm. Run each arm at least twice before comparing.
- Three runs, or three boot delays, for any figure that decides a default. Pair by route and delay and give the
  spread for complete pairs. At the same delivered ticks compare RNG, fighter state and work RAM. If a new feature
  writes RAM, identify the differing fields before claiming gameplay parity. Report how many checkpoints both
  arms reached and whether either stopped early.
- Give every run a time limit of its own. A run that hangs (a route stuck at a menu) otherwise holds an emulator
  slot until someone notices. Write the routes and settings that hang into the lane rules.

## What a run reports

Image hash, build flags, route or script, start and end vblank, fatals (code, PC), missing-tile counter, loads,
markers reached (stage words, clear flags), and stills. One line per run in the lane log.

## Stills

- Name stills by scene and vblank. Keep them outside git.
- **Still pair:** MAME at the same moment on the left, Saturn on the right. Use one before calling anything a bug:
  the AvP select-screen smear was the arcade's own effect.
- Look at stills yourself before reporting what they show.

## Host checks in the loop

Run every golden after any change to lifted code or the kernel. A host check of the whole game takes about a minute;
it covers most regressions faster than any emulator run.

For full or delta captures in the kit's golden format, run [golden_matrix.py](../../tools/golden_matrix.py) against the declared routes and delay labels. It checks paired IRQ numbers, record counts, work RAM and object RAM. Keep build identity, controller inputs, selected teams and performance counters in the run record. See the [tool examples](../../tools/README.md).
