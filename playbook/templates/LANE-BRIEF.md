# Lane brief: lane/<name>

**Goal (owner's words):** "<quote>"

**Deliverable:** <one sentence: what exists when this lane is done>

**Budget line:** <which row of the frame budget or backlog this moves, the gain expected, and the result that ends
the lane early>

**Premises, unproven:** <what this brief assumes that nobody measured. Check these in the first hour; tell the
coordinator at once if one is wrong>

**Size:** one question, about three hours. Half-way, send the coordinator two lines: what is proven, what is next.

**Already ruled out:** <what was tried or decided; link the STATUS.md section>

**Read first:**
- docs/STATUS.md, section <name>
- <files, notes, skill names>

**Resources:**
- Worktree: <path>, branch `lane/<name>` (from <base commit>)
- Evidence folder: <path outside git>
- Scratch: <scratch>/<lane name>/ only
- Emulator: own instance, MCP port <port>, own ini

**Scope:** touch only <files or folders>. Do not touch <other lanes' areas>.

**Gates:**
- Every change: build clean, host check on <goldens>, <flag-off identity>.
- Triggers that apply: <memory layout / logic / new stage / performance / release>.

**Safety:**
- `set -euo pipefail`; `${VAR:?}` on every rm (literal absolute paths where the tool refuses a variable); no
  generic script names; no inline `bash -c` with variables.
- No global input: own window or MCP only. Log every pid you start; stop only those, by pid, after checking name
  and start time. Check the machine load before every launch and wait when it is full.
- A/B controls play the same scene, keyed by game frame. Three runs for any figure that decides a default.
- A refused tool call: stop, report it, do not run a rewritten form.
- No game material in commits. Run `tools/hygiene_scan.py` before any push.
- Record the lane branch, base commit, backup policy and integration owner before work starts.
- Never end a turn waiting: poll your own job's marker with a bounded wait.

**Ask the owner only for:** looks, gameplay-visible choices, outward posts, deletions. Everything else: do it.

**Hand back:** use playbook/templates/HANDBACK.md. Hand back early with a resume list if context runs long. End
clean: no process left, intermediate images deleted, traps you found written into the lane rules.
