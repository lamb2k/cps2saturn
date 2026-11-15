---
name: saturn-release
description: Releasing a CPS2-to-Saturn port. Use when cutting a test or beta release, building the release disc from a test recipe, gating it, capturing release media, writing release notes and front pages, auditing a repo before making it public, publishing on GitHub, and updating a hosted web build with a rollback.
---

# Releasing a port

## Pick the disc, then freeze

- Release the newest disc that passed its gates, not the one the notes were drafted for. Check what each candidate
  holds before writing a word.
- Freeze scope when the candidate build starts. Late items go to the next release.
- Check for landed switches that are off in the recipe (see `saturn-perf`). Each is either turned on and gated, or
  parked with a reason.

## Build the release disc

- **Release disc = the test recipe minus test switches.** Debug readouts, build-id lines, profilers, self-tests and
  logs are compile-time switches; leave them all out. Never hide a readout with a memory poke or a crop.
- **Control build first.** Rebuild the test disc from the same tree with its own flags and compare. It should match
  except for ISO volume dates. That proves the recipe and work folder are the right ones before you change anything.
- List the final flags next to the test disc's flags, so the only difference is visible.
- Check memory budgets from the build log (fast RAM, slow RAM, cart tail). Removing switches should only free space.
- Record hashes for every track and for the zip you will publish.

## Gate the release disc itself

On the final bytes, in parallel:
- the static gates (VDP2 cycle check, alignment gate);
- game speed in the busiest early scene, read from emulated RAM, against the test disc;
- boot, title, each mode's entry, pause and quit to title, one still each, looked at by you;
- audio present (level check), and say nobody has listened if nobody has.
A non-blocking issue never blocks a release: list it in Known issues.

## Release media

- Capture from the release disc, with no memory pokes. Staging (health held, a setting changed, loading cut) is
  allowed only if the media's report lists it.
- Captions must be true of the captured build. Label emulator captures as such.
- Look at every still and at the clip's seams before using them.

## Release notes and front page

Write like a person talking to players, not like a status report:
- Lead with what it is in one plain sentence, then how to get it, what you need, and a clip and stills.
- Then what's in it, known issues, next up, and legal.
- No "it's not X, it's Y" lines, no bold label on every bullet, no internal words (lanes, recipes, gates, switch
  names, build ids), no em dashes.
- State hardware status plainly: what ran on a console, and what was only tested on emulators.
- GitHub release bodies keep every line break, so unwrap paragraphs, and use absolute links to files at the tag.
- Audit the whole README at each release, not just the top. Developer sections drift: dead links, old plans, and
  commands that no longer build the release.
- Template: `playbook/templates/RELEASE-NOTES.md`.

## Branches

- Lane branches often run far ahead of the default branch. Cut the release branch from the release disc's source
  commit, merge the docs branches into it, and make it the default branch.
- Other sessions (cloud or local) may have drafted notes or media on their own branches. Find and merge them before
  writing your own.
- Tag the release commit and push the tag before creating the release.

## Before a repo goes public

Going public exposes every branch and every commit, not just the default branch.
- Scan all history: `tools/hygiene_scan.py --history` for blocked file types, big blobs, private paths and keys.
- Check commit author emails, local paths and IP addresses in tracked files.
- Check the kit or tools repo too if it goes public at the same time.
- The rights decision, the licence and NOTICE wording are the owner's. Making a repo public can't really be undone.

## Publish

1. Push the release branch and tag; set the default branch.
2. Create the release (prerelease for a beta) with the disc zip and its SHA-256 in the notes.
3. Change visibility only after the release looks right.
4. Check as a signed-out visitor: front page, release images, asset download.

## Hosted web build

- Back up the live manifest (`build.json`) first; that file is the rollback.
- Upload image parts first and the manifest last, so visitors never load a half-written image.
- Uploads need the owner's direct yes in the main session.
- Test harnesses that scan fixed RAM ranges go stale when the layout changes. Derive ranges from the ELF or config.
- Check the live site boots the new image before calling it done.
