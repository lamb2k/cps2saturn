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
      release recipe nor parked with a reason and an owner. Move each forward or park it.
- [ ] **Quit and restart undo every runtime patch.** Dump patched tables after several restarts: 0 bytes differ.

## Measuring

- [ ] **Measure before optimising.** Profile the real image on a fixed build and scene. One variable at a time.
      Mean and tail (p95, max), whole frame, not only the target function.
- [ ] Roll back if p95 rises or the cost just moves elsewhere.
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
- [ ] "Done" means pushed plus checked. Say "coded, unrun" otherwise.
- [ ] Report what was not run as clearly as what was.

## Docs

- [ ] **STATUS.md is the one source of current state.** The backlog holds order, not state.
- [ ] Notes are marked Reference, Historical, Investigation or Draft. Old numbers never count as today's baseline.
- [ ] Record owner decisions the same turn.
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

- [ ] `${VAR:?}` on every `rm` with a variable. Own scratch folder per lane.
- [ ] No global input. Kill only processes you started.
- [ ] Outward-facing steps (publish, host, post) need the owner's OK unless a standing rule covers them.

## Release

- [ ] Freeze scope when the candidate build starts. Late items go to the next build.
- [ ] Build once, then run all checks on that one candidate in parallel.
- [ ] Package hashes recorded; boot from the package cue.
- [ ] Known issues listed; a non-blocking issue never blocks a release.
- [ ] Hardware status stated plainly.
- [ ] Release disc = test recipe minus test switches, with a control rebuild first. Media from the release disc.
      Full method: `saturn-release`.
