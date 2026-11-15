---
name: saturn-bonus-content
description: Adding home-only content to an arcade port without breaking the arcade game. Use for guest or bonus characters, new modes and options, swapped text and sounds, unlocks and backup-RAM saves, default-off switches with artifact-level identity proofs, donor-record data patching, memory budgets in size steps, fit gates, and making quit to title undo every runtime patch.
---

# Bonus content on an arcade port

Arcade mode with every bonus switch off is the product. Bonus content earns its place only if it can't change that.

## Switch policy

- Every addition sits behind a default-off build switch, and a runtime option where players choose it.
- **Identity with the switch off is proven on artifacts:** identical section binaries, an identical symbol table,
  and an ISO that differs only in volume dates and directory sectors. Also run the host goldens with the new code
  linked and the option off.
- Prove the harness really links the new code (AvP's host runner didn't, until fixed), and add a mutation control: a
  one-byte change must make the diff diverge.

## Measure the original before changing anything

- Measure what the arcade actually does (jump height per character, foot row against the floor line, hitstun
  lengths) and match it by default. Offer alternatives as default-off switches for the owner to judge.
- Census which animation slots and states the original reaches over long play before scoping a new character.
  AvP's donor reached 106 of 227 slots.

## Patch data, not code

- A new character copies the donor's whole record skeleton (durations, flags, hurt and attack box indexes, event
  bytes) and changes only what the new source names, usually the art pointers. Every state routine's contract then
  holds by construction. Forking state routines instead cost AvP about 160 tiles and was dropped.
- The engine may refuse hits unless a record names a hurt box. Imported boxes from another game can make states
  unhittable: check every state is hittable.
- Relocated data must be reachable through the lifted game's own address mapping. A raw Saturn pointer can't go in
  a 68000 address field.

## Identity must be latched

Never derive "which character is this" from a byte the game changes. AvP's death blink toggled the byte used as the
character id, so the guest reset every other frame and vanished at KO; in co-op the same byte was 1 for both
players and stripped the partner's gun. Latch identity while alive, and check it in one- and two-player games.

## Budgets come in steps

- Memory regions round to page or block sizes. AvP's cart tail rounds to 4 KB, which is 32 tiles: a 258-byte
  feature may cost nothing or a whole step. Report the margin to the next step, not just the bytes.
- Feature state in `.bss` lands in scarce RAM; put it in a region with room on purpose.
- **Fit gate before the build:** exit 0 pass, 1 fit fail, 2 bad input. Every mandatory key survives packing,
  additions don't raise the arcade's own tile loss, and the tightest stage is named.
- **Receipts for kept intermediates:** hash the generator inputs, layout and packer with the outputs. A mismatch
  forces a rebuild. The first build after adopting receipts rebuilds everything.

## Loading a character mid-stage

Stage files are often chosen by stage only, so a player who joins or continues as a character the stage file doesn't
hold gets no sprites. Reload on the live player's needs (with NOW LOADING), and forget per-pack caches when packs
swap, or the HUD keeps the old name and face.

## Text and sound swaps

- Keep new wording in your own code. Read the originals from the user's ROM at build time, and check each record
  against a short hash of the original before replacing it.
- Write swapped records only while the guest's files are loaded, restore them otherwise, and prove a no-op with the
  option off.
- A font cell draws blank unless its tile key is resident.
- Borrowed sounds: the same command number can mean different samples per character set. Attribute commands to the
  owning object where they're queued, and render them through the real driver after loading the right voice set.
- Speech recognition invents words. Label voice roles "by timing and ASR, not heard", and let the owner choose by ear.

## Unlocks and saves

- Use one backup-RAM file of your own: read, modify, write. A bad checksum falls back to the build default; format
  only an unformatted device.
- Give testers a QA-only way to reset unlocks.
- Test runs use a fresh save profile; a saved option can silently change a "default" run.

## Quit and restart undo everything

Quit to title and a new game must undo every runtime patch (code slots, tables, text, sound sets). Dump the patched
tables at cold boot and again after several quit and restart cycles: 0 bytes may differ.
