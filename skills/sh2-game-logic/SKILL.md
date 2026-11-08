---
name: sh2-game-logic
description: Game logic for CPS2-to-Saturn ports. Use for lifting 68000 code to C, boundary convergence (unresolved targets and jump tables), the translator semantics audit, the cooperative task kernel and IRQ placement, host differential checks against MAME goldens, the hybrid lifted-plus-readable architecture, readable C replacement of hot functions, and parity tests.
---

# SH-2 game logic: lift, prove, then make readable

## Hybrid architecture

1. **Lifted scaffold.** One C function per recovered 68000 function, against flat big-endian RAM at the original
   offsets. No interpreter fallback.
2. **Native kernel and hardware layer.** The game's cooperative tasks on real per-task stacks, the IRQ logic run
   from vblank in a fixed order, pads through the game's own latch.
3. **Readable C.** Function by function, hottest first, each one behaviour-gated against the lifted version and
   MAME, then swapped in.

Anything the native layer writes into game RAM stays big-endian at its original offset: the game reads what it
"shouldn't".

## First gate (before building the lifter)

Measure reachable code size, function count and computed jumps (whole game and round 1). Lift 100+ real functions
with SH-2 GCC -O2 and measure bytes per 68000 byte. Project against 2 MB work RAM + 4 MB cart, with and without
per-round overlays. Model the busiest tick's cycles, labelled MODELLED. Write GO or NO-GO.

## Boundary convergence

Iterate until zero unresolved call targets and zero unresolved jump tables:
- auto-detected tables plus a manual roots list that survives regeneration;
- functions reached only by pointer, addresses built in code, data between functions;
- targets entered by fall-through from code above;
- computed jumps where a call sits between the table read and the jump (easy to miss);
- odd branch targets are data decoded as code: emit UNHANDLED, do not lift.
A bad split must never pollute the accumulated target list. Scan for unresolved tables after every new route.

## Semantics audit

Generated-code checks per opcode and form, run against a reference 68000 core (Musashi or Unicorn), with a
deliberately broken generator proving the checks can fail. Cover X/N/Z/V/C flags, byte and word writes keeping
upper bits, predecrement/postincrement aliasing, movem, dbcc, large shift counts, BCD, sign extension of address
words. This is the biggest risk: translator defects surface late.

Generation guard: one wrapper generates output and writes a receipt (hashes of generator, inputs, output). Builds
refuse stale output.

## Host differential

- Run the lifted game on PC with a stub hardware layer, fed by the golden's logged I/O reads.
- Compare work RAM and object RAM per vblank. Report the first divergent dump and its writer.
- Take each IRQ at the same instruction MAME did (the golden records the interrupted PC and registers). Require
  work RAM, current task and object list to match the next dump before placing an IRQ at a kernel point.
- Mask only proven non-state: task save areas, stacks, the current-task pointer. Write the mask down.
- Goal ladder: attract, then round 1 to its boss, then the whole game to the ending, then other characters and
  two players. Keep every golden green after each change (AvP keeps six).
- A clean host run does not check cycle timing inside native kernel code. Say so.

## Readable C campaign

Disjoint lanes, hottest functions first. Each function: write readable C, run the behaviour gate (same outputs as
the lifted function over recorded inputs, plus the host check), swap in, report both sizes and both costs. Order
that worked: kernel, pools and spawn, damage, player, enemy AI per class, effects, route, boss.

## Home features in logic

New modes (duel, boss rush, stage select) sit behind build flags and touch the game through its own state: stage
words, spawn tables, health fields, credit byte. Normal play must stay byte-identical with the flags off: prove it
with the host check.

## Parity words

- **Functional parity:** same inputs give the same state trajectory, hits and animations. Testable.
- **Frame-exact parity:** identical framebuffers, needs exact RNG and rounding, fixed seed only.
Say which one a result proves.
