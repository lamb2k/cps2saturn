---
name: agent-orchestration
description: Running a CPS2-to-Saturn port with several AI agents at once. Use when planning lanes, writing a lane brief, launching or resuming lanes, landing lane work, handling shared resources (emulators, worktrees, disk), watching lanes for stalls, reading a hand-back, choosing models and effort, controlling cost, and deciding when to ask the owner and when to just do the work.
---

# Agent orchestration: one coordinator, many lanes

## Roles

- **Coordinator (the main session):** plans lanes, writes briefs, reads hand-backs, lands work, keeps STATUS.md and
  the backlog, talks to the owner. Does small lookups itself. Never spawns an agent for a check it can run inline.
- **Lane:** one agent, one deliverable, one owner area, one end point. Works in its own worktree on its own branch.

## Lanes

- Non-overlapping by files and by resources. Two lanes never edit the same file set.
- One agent per lane. If a lane needs two kinds of work, run them in sequence in that lane.
- Name lanes by intent (`lane/duel`, `lane/rounds`, `lane/audio`), not by number.
- Every lane has a worktree, a branch, an evidence folder and a scratch folder of its own. Never twin trees: two
  worktrees of the same branch, or two lanes building in one folder, give silent cross-talk.
- Lanes commit locally to their lane branch. The coordinator merges into the main branch and pushes. Lanes push
  their branch as WIP at least hourly so nothing is lost if a machine fails.

## The brief

A lane knows only its brief. Keep it tight and point at docs instead of retyping them:
- goal in the owner's words, and the deliverable;
- what is already ruled out;
- files and docs to read first;
- scope boundary (what not to touch);
- gates to run, and which heavier triggers apply;
- resources: worktree, branch, emulator port, evidence folder;
- safety lines (below);
- hand-back format.
Template: `playbook/templates/LANE-BRIEF.md`.

## Safety lines in every brief

- Own scratch subfolder named after the lane; no generic script names (`a.sh`, `run.sh`).
- `set -euo pipefail` in shell scripts; every `rm` with a variable uses `${VAR:?}`.
- No inline `bash -c "...$VAR..."`; write a script file.
- No global input. Own window or MCP only.
- No commits of game material; run the hygiene scan before any push.
- Kill only processes you started.

## Shared resources

- One emulator instance per lane, own port, own ini. Check the port owner before driving it.
- Builds saturate the host: cap parallel jobs. Cap the number of lanes running heavy jobs at once.
- Disk: each lane deletes its own intermediate images after its gates. Keep logs, hashes and the current package.

## Short runs and stall watches

- Checks run in a minute or two; long routes are legs joined by save states.
- A lane never ends a turn just waiting. It polls its own job's completion marker with a bounded wait.
- The coordinator runs a quiet-folder watch on each long lane (wake after ~10 quiet minutes) and checks whether
  the step finished. Tell the owner only what was measured; never say a lane is "progressing" without looking.

## Hand-back

Template: `playbook/templates/HANDBACK.md`. Lead with the result. Then: commits (hash and subject), what was proven
and at which tier, what was not, evidence paths, blockers, next steps as a resume list. A lane whose context is
getting long hands back early with that resume list rather than losing work.

## Verify before "done"

- "Done" means a pushed commit plus a passing check. "Coded, unrun" and "they say" are not done.
- Read the lane's evidence yourself before relaying it: the stills, the log tail, the hash.
- Re-run the cheapest gate on the landed result, not only on the lane's tree.
- An agent handed your hypothesis tends to return it confirmed. When you need an independent view, give the code,
  not the conclusion.

## Hand-backs are model output

A lane's report is a claim, written in the same confident voice whether it's right or wrong. Before relaying:
- look at the stills and logs it names;
- check one number yourself (a hash, a budget line, a count);
- watch for scope it quietly changed (a different base, an inferred work folder, a hidden assist) and ask why.
Lanes do surprising good work too: AvP's release lane rebuilt the test disc first to prove its recipe, unasked.
Keep that kind of control in the brief next time.

## Sessions end; work must not

- Before a pause, write a handover in the workspace: what is live, every open lane with branch, tip and next step,
  what was committed or pushed, and the traps found. Commit and push every dirty worktree as a WIP branch first.
- A resume reads the handover, then checks for work done since: newer branches, evidence folders, and notes from
  other sessions (local or cloud). The handover can be days stale.
- Keep a one-line pointer to the handover in the agent's memory index.

## Branches drift

Lane branches can run hundreds of commits ahead of the default branch while the front page sits on the default.
At each release, cut from the shipped source and make that the default; don't let the default branch rot.

## Permission and safety denials

When a tool call is refused (a permission prompt, a classifier, a hook), report it to the owner and stop that step.
Never route around it, and never ask a lane to do what the main session was refused. Some actions (uploads, making
things public) need the owner's direct yes in the main session; a lane can't get that.

## Cost discipline

- Every agent has a purpose, an owner area and an end point. No speculative or duplicate agents.
- Use stronger models for hard builds, debugging and design; cheaper ones for inventories, packaging, log scans.
  On AvP a mid-size model at high effort handled most lanes well (builds, gates, captures, research); the
  coordinator stayed on the strongest model to plan, review and land.
- Research that means reading dozens of notes is a good lane: ask for a ranked digest with the evidence and the
  target file, then write the result yourself.
- One agent with sequential steps beats several overlapping ones.
- Keep contexts small: brief by pointing at files. Suggest a fresh session at phase ends.

## When to ask the owner

Ask only for:
- how the game looks or plays (stills, gameplay-visible changes, feature design);
- outward-facing actions: making a repo public, hosting a build, posting to issues or forums;
- deleting user data or anything outside the disk-hygiene rule;
- pulling an item into a frozen release.

Do without asking: tooling and measurement fixes, research, diagnostic builds, clear bug fixes, disk hygiene,
internal docs. When one option is clearly better, take it and say so. Never ask what your own repro can answer.

## Record decisions as you go

When the owner decides something, write it down in the same turn: STATUS.md or the decisions list, the backlog,
and the agent file if it is a standing rule. Lost context must never lose a decision.
