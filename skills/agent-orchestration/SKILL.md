---
name: agent-orchestration
description: Running a CPS2-to-Saturn port with several AI agents at once. Use when planning lanes, writing a lane brief, launching or resuming lanes, landing lane work, handling shared resources (emulators, worktrees, disk), watching lanes for stalls, reading a hand-back, choosing models and effort, sizing lanes and checking a brief's premises, balancing speed and correctness lanes, running a retrospective, controlling cost, and deciding when to ask the owner and when to just do the work.
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
- Use the project's commit and backup policy. Record a lane's local tip and its remote branch when handing work back.
  Name the reusable change and the branch where the next port will be able to find it.

## The brief

A lane knows only its brief. Keep it tight and point at docs instead of retyping them:
- goal in the owner's words, and the deliverable;
- the budget line the lane is meant to move, the gain expected, and the result that would end the lane early;
- premises: everything the brief assumes that nobody measured, marked "unproven". The lane checks them in its first
  hour and tells the coordinator at once when one is wrong. A guess written as a fact sends a lane the wrong way;
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
- `set -euo pipefail` in shell scripts; every `rm` with a variable uses `${VAR:?}`. Where the agent tool's safety
  check refuses a variable in an `rm`, list the folders first and name each one by its literal absolute path.
- No inline `bash -c "...$VAR..."`; write a script file.
- No global input. Own window or MCP only.
- No commits of game material; run the hygiene scan before any push.
- Log every process you start (pid, name, start time). Stop only those, one pid at a time, after checking name and
  start time. Never by name or pattern: pids get reused and other lanes share the names.

## Lane size and check-ins

- One question per lane, about three hours. Lanes of five or six hours found their wrong turn at the hand-back, half
  a day late.
- At the half-way point the lane sends the coordinator two lines: what is proven, what is next.
- If the measurement a lane needs does not exist yet, the lane is the measurement. Don't build on a number nobody
  can read.

## Balance the lanes

- Keep at most two lanes that build and run emulators. More than that overloads the host and the disk, and the
  results arrive faster than they can be checked.
- One lane on speed, one on correctness. Two speed lanes for days left sound unwired and drawing faults open while
  the goal was the whole game.
- Order speed lanes by the size of their budget row (see `saturn-perf`), not by what is already half built. Four
  lanes went to a 3 to 5 percent item while a 12 to 20 percent loss sat unexplained.

## Shared resources

- One emulator instance per lane, own port, own ini. Check the port owner before driving it.
- Builds saturate the host: cap parallel jobs. Cap the number of lanes running heavy jobs at once.
- Disk: each lane deletes its own intermediate images after its gates. Keep logs, hashes and the current package.
- The host may be shared with other sessions and other projects. Set caps for the whole machine (emulators of each
  kind, builds, full translations), check the load with one script before every launch, and wait when it is full.
  When another project holds a cap for long, tell the owner. A lane never raises its own cap.
- Every run has its own time limit, so a hung run frees its slot by itself.

## Short runs and stall watches

- Checks run in a minute or two; long routes are legs joined by save states.
- A lane never ends a turn just waiting. It polls its own job's completion marker with a bounded wait.
- The coordinator runs a quiet-folder watch on each long lane (wake after ~10 quiet minutes) and checks whether
  the step finished. Tell the owner only what was measured; never say a lane is "progressing" without looking.

## Hand-back

Template: `playbook/templates/HANDBACK.md`. Lead with the result. Then: commits (hash and subject), what was proven
and at which tier, what was not, evidence paths, blockers, next steps as a resume list. A lane whose context is
getting long hands back early with that resume list rather than losing work.

## Lanes end clean

- Before the hand-back: no process of the lane is left (checked by pid against its log), intermediate images are
  deleted, and the hand-back says so. A job that could not be stopped is named with the time it ends.
- A trap a lane found (a route that hangs with pinned settings, a build that needs a fresh translation, a file a
  tool refuses to run without) goes into the project's lane rules in the same landing. Left in a hand-back, the
  next lane hits it again.

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
- watch for scope it quietly changed (a different base, an inferred work folder, a hidden assist) and ask why;
- treat a gate result as a claim too, pass or fail. One "failed" gate came from a control that played a different
  scene (its switch was poked by wall clock), and a whole lane was briefed on it. Ask for the evidence that both
  arms played the same scene before acting on the result.
Lanes do surprising good work too: AvP's release lane rebuilt the test disc first to prove its recipe, unasked.
Keep that kind of control in the brief next time.

## Sessions end; work must not

- Before a pause, write a handover in the workspace: what is live, every open lane with branch, tip and next step,
  what was committed or pushed, any local-only changes or evidence, and the traps found.
- A resume reads the handover, then checks for work done since: newer branches, evidence folders, and notes from
  other sessions (local or cloud). The handover can be days stale.
- Keep a one-line pointer to the handover in the agent's memory index.

## Branches drift

For a reusable result, check the kit's default branch and the lane diff. Squash merges can leave different
commit IDs with the same implementation. Compare files and tests before carrying a change over.
Move proven game-neutral tools, synthetic fixtures and their skill entry points together. Keep the per-game
addresses, captures and packs in the port. A new checkout should be able to find and test the common method
using the default branch. Record any genuinely unfinished lane and its remaining check in the handover.

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
- A switch that landed off needs an owner and a date: adopt it or delete the code. Built and undecided is cost with
  no gain.
- After a run of lanes, hold a short retrospective (keep, stop, start) and put its rules into the agent file, the
  lane rules and the brief template in the same landing. Rules that stay in a retrospective are not read.
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
