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
- **CD input level.** CDDA reaches the speakers through the SCSP's CD input send. AvP's per-stage sound swap cleared
  every slot's registers, including that send, while a cached "level already set" flag stopped the rewrite: CD music
  was silent from power-on until the first stage. Invalidate cached hardware state on every bulk register clear,
  and check music on the title, story and select screens, not only in a stage.

## Silent drops

Two of AvP's tools dropped sounds without saying so: the clip builder skipped clips over a length limit (so looping
sounds never played) and the budgeter dropped clips that had no table entry. Every drop must be counted and listed.

Coverage check: log every sound command the arcade issues per scene in MAME, then log the Saturn's outcome for each
(played, refused, missing from this stage). Rank the gaps by how often the arcade plays them.

## Fitting more clips

Pick a sample rate per clip. A clip with almost no energy above a lower rate's Nyquist (AvP: 1% bound) can drop to
8 kHz or 5.5 kHz with no audible loss; bright sounds and voices keep 11 kHz. Keep level (RMS) and pitch (the clip's
rate sets the SCSP octave and frequency). AvP saved 21.6% and fit back almost all the sounds it had dropped.

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
