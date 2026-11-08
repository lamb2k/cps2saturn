# CPS2 to Saturn playbook

How to take a Capcom CPS2 arcade game to a native Sega Saturn build with the 4 MB RAM cart, with a coordinator
and several AI agent lanes doing the work. Intended for software preservation efforts, from material you are
authorized to use.

The skills under `skills/` hold the technique for each area. This file holds the order, the gates, the staffing
and the lessons.

## 1. The shape of a port

```
ROM set (local, never committed)
  -> MAME 0.289 reference: goldens, routes, census
  -> lifted 68000 program as C (host-checked against MAME)
  -> native Saturn layer: pads, VDP1/VDP2, SCSP/CDDA, CD loads, cart residency, two SH-2s
  -> readable C for hot and unclear functions
  -> home features behind flags
  -> ISO + cue + CDDA, hardware test sheet
```

Rules that hold throughout:
- MAME is the reference for behaviour. The Saturn build never runs a CPS2 emulator.
- Game logic consumes current state and current input, never captured frame labels.
- Evidence tiers stay separate: HOST, MAME, EMULATOR, HARDWARE. MODELLED for estimates.
- STATUS.md is the one source of current state. The backlog is order only.

## 2. Phases and gates

### Phase 0: identity

Work:
- Audit the ROM set in the pinned MAME. Record set name, description, MAME build.
- Fill `configs/<set>.yaml` (see `configs/avspu.example.yaml`).
- Dump program and opcode spaces; build the merged image.
- Find the game's debug features (hitbox display, info monitors, test menus).
- List inputs (`tools/mame/list_inputs.lua`).
- First golden: attract mode, a few thousand IRQs.

Gate: ROM audit clean, config filled, golden recorded with its hash, debug features listed (or "none found").

### Phase 1: first gate (go or no-go)

Work:
- Reachable code: size, function count, computed jumps, whole game and round 1.
- Lift 100+ real functions; SH-2 GCC -O2 bytes per 68000 byte.
- Project fit: 2 MB work RAM + 4 MB cart, with and without per-round overlays.
- Modelled cycles for one busy tick.

Gate: a written GO or NO-GO with numbers, labelled MODELLED. The owner sees it.

### Phase 2: translator

Work: lifter, boundary convergence to 0 unresolved targets and tables, semantics audit against a reference
68000 core, generation receipts.

Gate: audit suite passes; a frozen-bad generator fails it; zero unresolved on the attract golden.

### Phase 3: host check

Work: host runner with a stub hardware layer fed by the golden's I/O log; per-vblank compare of work RAM and
object RAM; IRQ placement at the recorded instruction; the non-state mask written down.

Gate ladder (each is a gate):
1. attract clean;
2. round 1 to the boss clear, with KO and continue, clean;
3. whole game to the ending clean;
4. other characters and two players clean.
Every later change keeps every golden green.

### Phase 4: Saturn layer, first playable

Work: sprites to VDP1, scroll layers to VDP2, palettes, pads through the game's latch, audio hooked, slave SH-2
drawing, the memory map with real numbers.

Gate: round 1 start to boss clear on the emulator with real pad input (scripted or bot, pad only), host check
green to the same point, image hash recorded.

### Phase 5: whole game, fit and speed

Work: census of every stage over many routes; round files from CD; shared pages; drop ranking; missing-tile
counter; profile and readable C for hot paths.

Gate: whole game to the ending on the emulator image (legs joined by save states are fine; say so), dropped
keys reported per stage, frame cost measured and labelled.

### Phase 6: home features

Work: title menu, options, sound test, music player, NOW LOADING, home modes. See section 6.

Gate per feature: a pad-only run shows it working; with its flag off, the host check and normal play are
unchanged; the owner has seen stills of anything visible.

### Phase 7: release

Work: clean package build, disc budget, hashes, hardware test sheet, notes with stills, known issues.

Gate: package built clean from a recorded commit; booted from the package cue; hashes recorded; the release
notes state hardware status plainly (UNRUN until the owner runs it).

## 3. Staffing and briefing lanes

### Who does what

- **Coordinator:** one main session. Plans, briefs, lands, reports. Does small checks itself.
- **Lanes:** one agent each, one deliverable each, own worktree, branch, evidence folder, scratch folder and
  emulator port.

### Lanes that worked on AvP

| Lane | Owns |
| --- | --- |
| translator | lifter, roots, audit suite |
| golden | MAME routes and goldens, census per stage |
| satint | joining the lifted game with the Saturn layer |
| satgfx | tile packs, VDP1/VDP2 adapters, screen fit |
| audio | sound table, SCSP clips, CDDA tracks, capture compare |
| rounds | round files, shared pages, drop ranking, store |
| home | title menu, options, sound test, music player, boss rush |
| duel | duel mode rules, arena, HUD |
| web | browser test build (local until the owner approves hosting) |

Run as many lanes as have clear, non-overlapping deliverables. Cap how many run heavy builds or emulators at once.

### Writing the brief

Use `templates/LANE-BRIEF.md`. Point at files rather than retyping them. Name the gates. Put the safety lines
in every brief. State the end point.

### Landing

- Lanes commit to their lane branch. The coordinator merges, runs the cheapest gate on the merged tree, pushes.
- Before merging a branch that once reverted something, diff the stat first: a merge can replay a revert.
- After a merge, rebuild the package clean and boot it before calling the merge done.

### Watching

- A quiet-folder watch per long lane wakes the coordinator after ~10 quiet minutes.
- On a wake: did the step finish, what does the log say, message the lane to continue.
- Report only what was measured.

## 4. Gates per change (lean) and on triggers (full)

Every change:
- build clean, no unresolved symbols;
- host check on the goldens the change can touch (all of them for lifted code or kernel changes);
- for a flag-gated feature, flag off gives an identical image or a proven-identical host run;
- one short emulator run if the Saturn side changed.

Full tier, only when triggered:
- memory layout or image size change: whole-route emulator run, missing-tile counts per stage;
- logic change: every golden, plus a changed-input route;
- new stage or mode: pad-only run through it;
- performance decision: same build, same scene, one variable, mean and tail;
- release candidate: everything once, on the final image.

Humans judge looks, feel and pacing. Computers judge identity, memory headroom, frame cost and fatals.

## 5. New-game setup checklist

- [ ] Confirm you are authorized to use the ROM set. Record that in the project's NOTICE.
- [ ] Private repo for the game; this kit as reference. `.gitignore` blocks game material from the first commit.
- [ ] Pin MAME; audit the set; record the build.
- [ ] Pin the SH-2 toolchain, the Saturn library and the emulator build (with MCP bridge). Record versions.
- [ ] Copy `configs/avspu.example.yaml` to `configs/<set>.yaml`; fill set name, ROM files, region sizes.
- [ ] Find: IRQ entry and vector, work RAM and object RAM ranges, I/O ranges, input ports, stage word, round
      byte, clear flags, credit byte, health fields. Add each to the config as you find it.
- [ ] Dump program and opcode spaces; build the merged image.
- [ ] Record the attract golden; check its replay is deterministic (run twice, same hash).
- [ ] Write STATUS.md, BACKLOG.md and the agent file from `templates/`.
- [ ] Decide evidence folders outside git, one per lane.
- [ ] Set up the hygiene scan as a pre-push step.
- [ ] Run phase 1 before building anything big.

## 6. Home features: Capcom Saturn conventions

Capcom's own Saturn ports (the fighters especially) set the expectations for a home menu. Follow them so the port
feels native:

- **Main menu over the game's own title:** ARCADE, then the home modes, then OPTIONS. A header names the screen.
  A translucent panel (VDP2 colour calculation) under the logo, the game's own font, no new art.
- **OPTIONS:** GAME (difficulty, continue, time), BUTTONS (button config per action), SOUND (stereo/mono, music
  player, sound test), SCREEN ADJUST (move the picture a few pixels each way). B goes back one level; Start leaves
  an option page.
- **Credit without coins:** set the game's credit byte; no coin sound.
- **NOW LOADING:** in the game's font, bottom right, through every stage file load, gone before the stage picture.
- **Music player:** the game's songs by name, on their CD tracks.
- **Sound test:** any command id through the game's real sound path.
- Options reach the game through its own state bytes; prove each one reaches play.

### Home modes as examples

- **Boss rush:** the game's bosses in order, each fight starting at its boss. Use the stage words and spawn tables
  the game already has. Carry health between fights (take it before the game's own stage-clear refill). A card
  between fights ("FIGHT n OF 5") in the game's font, and a result screen with times. Leave out bosses that would
  need the camera, spawn pointer and scroll layers set together; say why.
- **Duel (player against player):** a stage as arena with its spawn table parked, the camera held at the arena
  lock, a depth margin so beat-'em-up lanes can connect, damage percent and stocks HUD, knockback growing with
  percent, hitstun, hit-freeze, ring-out with respawn and invulnerability flashes, sudden death on time out. Menu:
  stocks, time, aliens, arena. Test each menu value, not only the defaults.
- **Stage select:** start at any stage word by replacing the start path's first stage.

Each mode sits behind a flag. Normal play with the flags off stays byte-identical.

## 7. Lessons from AvP

Alien vs. Predator (`avspu`) to Saturn: lifted game, whole game on host to the ending, Saturn image through the
ending on the emulator, home modes. What it taught:

1. **The KEEP_ROUND_FILES trap.** A test switch kept last build's round files to save build time. When code moved,
   kept files restored stale cold code (black stages, fatals) and later overwrote tile spills with ROM bytes (121
   of 210 files wrong on one kept rebuild; wrong tiles on crates in two stages). The "tile bug" did not reproduce
   on a clean build. Rule: kept intermediates only for kernel-only test builds, check layout ends match, never
   package from one, and re-check any visual bug on a clean build first.
2. **ROM pages are shared between stages.** Spilling tiles into ROM pages a stage does not read is a big win, but
   another stage, a mode or a setting may read them. The duel read stage 02's pages on every arena and drew noise
   blocks; a census of normal play never saw it. Keep pages most stages read in every file, restore every page a
   file overwrites for each stage that reads it, census every mode, and trap dropped-page reads on host.
3. **The disc over CD-R and the shared store.** 210 round files plus 26 CD tracks came to about 372,500 sectors,
   over an 80-minute CD-R. The shared sector store cut the data track from 240,771 to 94,143 sectors with every
   round byte-identical. Count the budget early; dedupe before cutting content.
4. **Pad-only proofs, not memory-poke bots.** A bot that set boss health over MCP proved the boss rush's flow but
   not its play. Label such runs DIAGNOSTIC and prove features again with pad input alone.
5. **Select screens.** A garbled portrait on entering character select turned out to be the arcade's own smear in
   its first second. A MAME still pair closed it. Pair before fixing.
6. **Check history before solving.** A full-width screen fit already existed in an older engine branch; audio
   reported "missing" had only been switched off in runs. Search all branches first.
7. **Emulator speed drifts.** Yaba slowed from ~60 to ~20 vblanks/s within a minute in some scenes; a fresh process
   restored it. Long routes ran as legs joined by save states, reported as such.
8. **One emulator per lane.** Two lanes both saw a port free and started; one bot drove the other's machine. Check
   the port's owner pid.
9. **Jump tables the map misses.** Fatals in later stages came from computed jumps with a call between table read
   and jump, and from a side store that cut byte tables at 256 bytes. Scan for unresolved tables after each route.
10. **Capcom menu conventions** made the home build feel right at once (section 6). NOW LOADING and the music
    player were cheap and much noticed.

## 8. Templates

- [Lane brief](templates/LANE-BRIEF.md)
- [Hand-back](templates/HANDBACK.md)
- [STATUS.md](templates/STATUS.md)
- [Release notes](templates/RELEASE-NOTES.md)
