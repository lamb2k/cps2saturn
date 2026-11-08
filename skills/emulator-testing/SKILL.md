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
- **HARDWARE:** a real Saturn with the 4 MB cart. Only the owner can produce this. UNRUN until then.
Never let a lower tier advance a higher tier's status.

## The Yaba MCP harness

A debug build of Yabasanshiro serves an MCP endpoint on a local port: memory reads and writes, screenshots and
(with a small patch) pad state. `tools/yaba_mcp.py` holds the client.

- **One instance per lane.** Each lane gets its own emulator folder with its own ini and its own MCP port. Check the
  port's owner pid before driving it: two lanes can both see a port free, start, and one bot then drives the other
  lane's machine.
- **Own window only.** Pad input goes to the emulator's own window handle (PostMessage key down/up) or through the
  MCP pad call. Never use global input (SendKeys, keybd_event, SendInput).
- Retry reads that answer empty while the core starts or during a long CD read.
- Restore the user's emulator settings after the run; edit a copy of the ini, never the user's only copy.
- Memory writes take bytes as a hex string; a list of ints may silently write nothing.

## Pad-only proofs

A proof of play uses only real pad input through the game's own latch.
- **Scripted pad:** a fixed schedule compiled in or played by the harness. Good for repeatable smoke runs.
- **Closed-loop bot:** reads RAM over MCP (read only) and picks keys. Good for getting through a stage.
- **Memory-poke bots are diagnostics,** not proofs. If a run sets health or boss state over MCP, label it
  DIAGNOSTIC and do not count it as play. Prove the same feature again pad-only.

## Short runs

Most checks should take a minute or two. Long runs drift (Yaba slowed from ~60 to ~20 vblanks/s within a minute in
some scenes; a fresh process restores speed). Join long routes as legs with save states, and say so. Bound every
run with a timeout and kill only the processes your run started.

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
