---
name: best-practices
description: Checklist of working rules for CPS2-to-Saturn ports. Use before landing a change, cutting a release, proposing an optimisation, reporting results, or setting up a new project: data-driven code, measure first, byte-identity proofs for build changes, feature flags that keep normal play unchanged, front pages and release notes with stills, disk hygiene, evidence labels and repo hygiene.
---

# Best practices checklist

## Code

- [ ] **Data over hard-coding.** Game constants (set name, addresses, stage tables, IRQ entry, RAM ranges) live in
      the per-game config, not in tool code.
- [ ] **Generated files are generated.** Never hand-edit generated headers or tables; fix the generator.
- [ ] **Feature flags keep normal play unchanged.** Every home feature and test option is behind a build flag.
      With the flags off, the host check is byte-identical and the image hash matches the previous build where
      the change claims no effect.
- [ ] **Byte-identity proof for build changes.** A refactor, store, packer or layout change proves its outputs are
      byte-identical to before (rounds rebuilt from the store, ISO members compared, host goldens clean).
- [ ] **Identity is proven on artifacts:** with a switch off, identical section binaries and symbol table, and an
      ISO that differs only in volume dates. Plus a mutation control showing the check can fail.
- [ ] **Test switches never ship.** Builds that keep stale intermediates (kept round files and the like) are for
      quick tests only and are never packaged. Debug readouts, profilers, self-tests and logs are compile-time
      switches, off in every release recipe. Never hide one with a memory poke or a crop.
- [ ] **No landed-but-off switches without a reason.** Keep a list of every landed switch that is neither on in the
      release recipe nor parked with a reason, an owner and a date. Move each forward, park it, or delete the code.
- [ ] **Quit and restart undo every runtime patch.** Dump patched tables after several restarts: 0 bytes differ.

## Measuring

- [ ] **Measure before optimising.** Profile the real image on a fixed build and scene. One variable at a time.
      Mean and tail (p95, max), whole frame, not only the target function.
- [ ] Roll back if p95 rises or the cost just moves elsewhere.
- [ ] **Build the measurement before the work.** A fixed benchmark scene that plays the same on every build (input
      keyed by the game's own tick, opponent and random state pinned) comes before the first speed lane. Without
      it the opponent's choices follow the layout and the load timing, and real cuts read as noise.
- [ ] **A whole-frame budget picks the work.** Work per game tick per scene against the cycles in a frame, biggest
      row first. Each change names its row and the gain it expects.
- [ ] **An unexplained gap is a task.** When two measurements that should agree do not (benchmark against normal
      play, model against console), find out why before anything else. Such a gap hid one port's biggest gain.
- [ ] **Three runs for a decision,** with the spread. Layout and load timing move a figure by 1 to 3 percent; one
      run inside that is "indicative", not a result.
- [ ] **A control plays the same scene.** Key switches and memory pokes by game tick, never by wall clock, and show
      that both arms reached the same state (same picks, same stage, same start frame).
- [ ] **Savings are hypotheses** until measured. Check what the build already has before calling something untried.
- [ ] Label every number: HOST, MAME, EMULATOR, MODELLED, ASSUMED, HARDWARE (CONSOLE).
- [ ] Record build, commit, scene, window, flags, emulator copy and settings, and asset path with every comparison.
- [ ] **A clean emulator run is not a console result.** Memory placement, VDP2 timing, misalignment and power-up
      state only show on hardware. See `saturn-bringup` and `saturn-perf`.
- [ ] Know which clock a counter counts. Game ticks against the arcade's own rate, not "frames done".
- [ ] Keep load, KO and continue windows out of speed figures. Fresh save profile per run.
- [ ] No percentage confidence from reasoning. Expected outcomes per case, a risk register, corrections in place.

## Evidence

- [ ] Look at the stills and logs yourself before reporting.
- [ ] Still pairs (MAME left, Saturn right) before calling something a bug.
- [ ] Pad-only proofs for features; memory pokes are DIAGNOSTIC.
- [ ] **Four states, kept apart:** implemented (landed and pushed), tested (at a named tier), accepted (the owner
      says it looks and plays right) and released (in a published build). Record each separately. A landed fix
      that is off in the release recipe is implemented, not released. A closed issue is not an accepted fix.
- [ ] "Done" means pushed plus checked. Say "coded, unrun" otherwise.
- [ ] **Not reproduced is not fixed.** A failed reproduction proves nothing until the same route reproduced the bug
      before the change. Forcing a fault (a memory poke, a widened window) shows the old fault is gone, not that
      the new code is safe.
- [ ] Scale the testing to the change: one smoke run for a small change, the full set when a gate or a release
      needs it. A/B comparisons keep a baseline and run in ABBA order so drift cancels.
- [ ] On looks, the owner's eye beats a metric. Say which build and settings are on screen.
- [ ] Report what was not run as clearly as what was.

## Docs

- [ ] **STATUS.md is the one source of current state.** The backlog holds order, not state.
- [ ] Notes are marked Reference, Historical, Investigation or Draft. Old numbers never count as today's baseline.
- [ ] Record owner decisions the same turn.
- [ ] Each fact lives in one place; other docs link to it. Old notes keep their conclusions; a later finding adds
      a dated correction line instead of rewriting them.
- [ ] **Front pages and release notes:** each release updates the README "At a glance" and "What's new", keeps a
      "Coming soon" for the next build, and shows a still of each visible change (labelled emulator or console).
      Stills of game screens stay out of the public kit; in a game repo they go only where the owner allows.
- [ ] Plain words, short sections, no walls of text.
- [ ] **Public text reads like a person wrote it.** No "it's not X, it's Y", no bold label on every bullet, no
      internal words (lanes, gates, recipes, switch names), no em dashes. Agent-facing docs stay out of the front
      page, or get a plain one-line description.
- [ ] Audit the whole README at each release: dead links, old plans and build commands that no longer build it.

## Repo hygiene

- [ ] Never commit ROMs, extracted data, captures, stills of game screens, images or packages.
- [ ] Run `tools/hygiene_scan.py` before every push: file types, sizes, binary content, private paths, keys.
- [ ] Before a repo goes public, run `tools/hygiene_scan.py --history`: every branch and commit becomes public.
      Check commit author emails too.
- [ ] No private paths, host names, IPs, tokens or keys in code or docs. Use config or environment values.
- [ ] Commit in logical steps. Never force-push a shared branch.

## Disk hygiene

- [ ] Delete rebuildable outputs (object folders, staged images, intermediate packages) at phase ends and when a
      drive runs low. Lanes delete their own intermediates after their gates.
- [ ] Keep source, unpushed work (bundle it first), logs, hashes, goldens referenced by tests, and the current
      package. Write a manifest of what was deleted.
- [ ] Keep evidence and its cache on the same drive when tools hard-link.

## Safety

- [ ] `${VAR:?}` on every `rm` with a variable, or literal absolute paths where the agent tool refuses a variable.
      Own scratch folder per lane.
- [ ] No global input. Stop only processes you started, by the pid you logged at launch, after checking name and
      start time, never by name (`pkill -f`, `taskkill /im`). See `emulator-testing` for emulator claims and
      file backups.
- [ ] A refused tool call is reported, not rewritten into a form that passes.
- [ ] Outward-facing steps (publish, host, post) need the owner's OK unless a standing rule covers them.

## Release

- [ ] Freeze scope when the candidate build starts. Late items go to the next build.
- [ ] Build once, then run all checks on that one candidate in parallel.
- [ ] Package hashes recorded; boot from the package cue.
- [ ] Known issues listed; a non-blocking issue never blocks a release.
- [ ] Hardware status stated plainly.
- [ ] Release disc = test recipe minus test switches, with a control rebuild first. Media from the release disc.
      Full method: `saturn-release`.
