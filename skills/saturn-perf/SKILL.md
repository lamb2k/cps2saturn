---
name: saturn-perf
description: Making a CPS2 port run at full speed on a real Saturn. Use when the console is slower than the emulator, for picking what to optimise, modelling memory placement cost, placing hot code and data in fast RAM, measuring game speed against the arcade's own tick clock, a whole-frame budget per scene, a fixed benchmark, ticks lost to an early frame interrupt, disc waits that look like slow code, slave draw budgets in field units, removing repeated work, and proving a speed change keeps behaviour exact.
---

# Speed on a real Saturn

## Emulators hide the real cost

Most Saturn emulators charge one flat cost per memory access and nothing for instruction fetches. A Saturn doesn't:
a 16-byte cache line fill costs about 7 clocks from high work RAM and about 56 from low work RAM, and the cart bus is
slower again. So code or data sitting in low RAM or the cart can make the console two to three times slower than the
emulator in the same scene, and the emulator will never show it.

- Build or patch a region-aware cost model (cache fills per region, cache-through accesses, write buffer), label its
  numbers MODELLED and figures you couldn't find published ASSUMED, and calibrate it once against a console photo of
  the readout. AvP's model, set from published figures and not fitted, reproduced the console's missed pictures in
  the busiest stage.
- A uniform "slow the CPU down" factor can't see placement, so a placement fix shows no gain under it. Don't use it
  to judge one.

## Know which clock you are measuring

- Find the game's own gameplay tick counter on the arcade reference first, and measure ticks per 60 vblanks there.
  CPS2 games usually catch up after a late tick, so a late tick may cost no game time.
- A task-walk or "frame done" counter is not game speed. Name each counter for what it counts.
- Keep four measures apart: host speed, game work per tick, presentation (new, held and skipped pictures) and
  animation. A held-picture percentage is not missed game frames.
- Windows that contain a load, KO or continue read high or low. Keep them out of speed figures.
- Put the speed counters on an on-screen readout behind a compile-time switch, with the build id, for console photos.
  The readout costs fast RAM (AvP: about 2.8 KB), so it never ships in a release build. The kit's `saturn/rt/sat_readout.c`
  is that readout without the game: PIC, DONE, MISS, SKIP, HELD, TICK (your game's tick byte, from your config, per 60
  vblanks), a PROF line and the `HW SND n OK TEST t` power-up line; you give it counters and a cell callback. Label every
  figure from a photo HARDWARE and keep the first console disc's photo checklist next to it.

## A budget for the frame

- A frame has a fixed number of master cycles (about 477,000 at 28.6 MHz and 60 Hz). Keep one table per benchmark
  scene: the game's work per tick, as cycles and as a share of a frame, and what makes the master wait (disc,
  the other CPU, loads).
- A tick fits when the work fits in one frame and nothing makes the master wait. A scene at 110 percent of a frame
  cannot reach full speed by removing waits; a scene at 75 percent needs only the waits removed. The table says
  which lane a scene needs.
- Split "work" by class before cutting: translated game code, table and ROM lookups, overlay calls, the scheduler,
  the hand-off to the slave, video work in the real vblank. Cut the biggest class first.
- Treat a modelled figure as a lower bound of the console's cost and leave a margin. Only a console photo sets it.

## A fixed benchmark

- Make one fight (or scene) per route that is the same on every build: input script keyed by delivered game
  interrupts, opponent picks, stage and random state pinned at a defined game frame, behind a build switch that
  is off in release images. Prove it: two different layouts of one tree reach the same game state at the same frame.
- Before it existed, five lanes in a row made real cycle cuts and each read "within noise" in game ticks.
- A benchmark has a bias. If it delivers interrupts or loads differently from normal play it is for A/B only, and
  the result that counts is normal play. Ask why the two differ: the answer may be the biggest item you have.

## Lost ticks: the frame interrupt that arrives early

CPS2 games run their frame work as scheduler tasks that the vblank interrupt wakes. On the arcade the interrupt
lands while the game idles. On a slower machine it can arrive before the last round of frame tasks has finished:
then it wakes nothing and that tick is lost, although the master did the same work.

- Measure game ticks per delivered interrupt. Under 1.0 means lost ticks. One port read 0.80 to 0.88 in fights.
- The fix: the real vblank does its video work at once and queues the game's interrupt; the scheduler delivers it
  at the first pass in which no task did more than poll. Cap the delay (two vblanks), after which it is delivered
  the old way. Nothing is dropped or merged, and the pad word travels with its interrupt.
- That port went from 45 to 52 game ticks a second to 52 to 59 (MODELLED, console unrun), its largest single gain,
  with no cut in master work.
- Prove gameplay, since timing moved: every interrupt and every input row delivered exactly once, the same mode
  sequence on long runs, and a build that drops interrupts on purpose must be caught by the check.
- The cost: each picture now carries more game ticks, so the slave's work per picture rises. Check pictures a
  second again afterwards.

## Waits that look like slow code

- Sample the master's program counter inside the stalls before naming a cause. A wait log that stamped waits one
  vblank late blamed the slave's pictures; the samples showed about 90 percent of the waiting was masked disc reads.
- A demand read of one sector costs about two frames with a 2x drive (MODELLED). Count disc accesses in a fight,
  not bytes: read whole sectors into the cache, load what a match needs before it starts, and look for two code
  groups that keep evicting each other from one slot.

## Place code and data by measured heat

- Profile many scenes, rank functions by cost per byte, and fill fast RAM with the hottest. Never demote code that
  already ran in fast RAM.
- Credit every alias of a function (split bodies, local symbols). One mis-keyed alias left AvP's hottest function in
  slow RAM.
- Put compiler runtime helpers (division, shifts, memcpy) in fast RAM too; hot code calls them constantly.
- Stacks and per-frame hot data go in fast RAM. A snapshot the slave reads every vblank should not live in low RAM.

## Measure the cost at the caller

Count calls, accepted work per call and declined calls on the game routes. Include argument preparation, fallback
and placement overhead when comparing a fast kernel to the existing path. Compare a hot copy with ordinary
resident code given the same fast-RAM budget. Record both the affected cost category and the whole-tick result.

## Remove repeated work first

The biggest exact win is usually work done again for nothing. AvP redrew its whole text layer on any change, and
the costly part was a per-row fit computed again for rows that never change. Memoise, skip blank rows, then redraw
only dirty rows (re-stamp clean rows' cache slots first, or an eviction corrupts them). Pictures per second went
from 40 to 60 in the busiest scene (MODELLED).

Gate each such change with an exact host test (a hash of the resolved layer per frame) and a mutation check that
proves the test can fail.

## Slave draw budget

The slave draws from a snapshot. A draw that runs past one field loses the whole picture, so work in field units and
read the draw-length distribution (mean, p99, share over one field), not the mean.

## Small ideas lose on the real driver

Command pairing, slot hints and command shadows all measured slower in AvP's emulator runs once the whole frame was
counted. Don't adopt a graphics micro-optimisation without a measured whole-frame win, and say which tier measured it.

## Prove a speed change keeps behaviour

- Drive scripted input by the game's own tick counter, not by vblank. Otherwise a layout change shifts the first
  frame and the state diverges for reasons that have nothing to do with the change.
- Compare under a flat cost model too: a placement-only change should be cycle-identical there.
- Under stock timing, expect differences only in stack scratch bytes, and whitelist exactly those.
- Run the same build twice as a control.

## Traps

- **Landed but off.** Two exact speed fixes sat default-off for days and were missing from the console discs. Keep a
  check that lists every landed switch that is neither on in the release recipe nor parked with a reason. Give
  each a date: adopt it or delete the code.
- **A control keyed by wall clock.** A switch poked "after two seconds" lands at a different game frame in each
  image, so the two arms play different fights. Key it by game frame.
- **One run.** Layout and load timing move a figure by 1 to 3 percent. A default is decided on three runs.
- **Small exact wins before the big cause.** Four lanes made a per-vblank copy exact and cheap for 3 to 5 percent
  while lost ticks cost 12 to 20. Fill in the budget table first.
- **Bisect one change per arm.** "Only slow with the extra character" turned out to be the test's "stock" character
  being the extra one in that slot.
- **Fresh profile per run.** A saved setting in the emulator's backup RAM silently turned a feature on in a
  "default" run.

## Code in the kit

`saturn/rt/sat_sync` is the master and slave hand-off, `saturn/gfx/sat_layer` skips unchanged layers, and `tools/fn_heat.py` with `tools/place_plan.py` place hot functions in the fast RAM from a measured heat file. Timing claims still need a console measurement; the host tests do not give one.
