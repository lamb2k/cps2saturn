---
name: saturn-audio
description: Audio for CPS2-to-Saturn ports. Use for moving QSound effects to SCSP PCM, music to CDDA tracks, the game's sound command path, per-channel versus mixed-stream playback, SCSP RAM budgets per stage, the sound test and music player in home menus, and comparing emulator audio output against MAME.
---

# Saturn audio for CPS2 ports

## Shape

- **Music to CDDA.** Render each song from MAME to 44.1 kHz stereo and put it on the disc as audio tracks. Cap the
  render length (AvP used 80 s with a loop) to fit the disc budget.
- **Effects to SCSP PCM.** Extract each QSound effect sample, resample to an SCSP rate, and load the stage's set
  into SCSP RAM at stage load.
- **Keep the game's command path.** The game sends sound commands through a ring or mailbox (AvP: 63 entries,
  silent drop when full). Hook that path natively: a command becomes a music track start or an SCSP voice. The game
  logic never knows the difference.

## The sound table

The Z80 driver's table gives each command's class (music, effect, direct), priority and channels. Decode it once
per game into JSON (counts only, no sample data in git). Use priority for voice stealing.

## Per-channel or one stream

- **Per-channel slots:** cheap (AvP worst 0.10 ms per frame on the emulator timer).
- **One mixed stream:** closer to the arcade mix by envelope correlation, but ~20x the cost.
Measure both on your game with `tools/audio_compare.py` before choosing. State that the numbers are EMULATOR tier;
Yaba may undercharge bus reads.

## Budgets

SCSP RAM is 512 KB, shared by driver, buffers and samples. Per stage, list the clips it needs; when over, drop by
priority and report what dropped. Load clips at stage boundaries only.

## CDDA rules

- Find the exact frame music starts by reading the state machine. The last legal data read is before it.
- Avoid CD data seeks while CDDA plays unless the runtime path is measured safe. Load first, then start music.
- After a load, restart the stage's music track.

## Sound test and music player

Home menus in Capcom Saturn ports have a SOUND page:
- **Sound test:** any command id through the game's own mailbox path, so it tests the real hook.
- **Music player:** the game's songs by name, mapped to CD tracks. Start leaves the page.
Both must work after pause, quit to title and a new game.

## Checking

- Emulator capture: a patched emulator that dumps raw SCSP output is the best tier short of hardware. Compare
  against MAME's WAV of the same script: silence share, best offset, envelope correlation, level in dB.
- A non-silent capture with matching clips is not a listening test. Say "no person has listened" until one has.
- Runs with sound off are "audio unchecked", not "audio missing". Write which it was.
- Rapid retriggers must not leak voices; test a burst of the same effect.
