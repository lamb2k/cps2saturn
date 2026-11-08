# Lane brief: lane/<name>

**Goal (owner's words):** "<quote>"

**Deliverable:** <one sentence: what exists when this lane is done>

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
- `set -euo pipefail`; `${VAR:?}` on every rm; no generic script names; no inline `bash -c` with variables.
- No global input: own window or MCP only. Kill only processes you started.
- No game material in commits. Run `tools/hygiene_scan.py` before any push.
- Commit to the lane branch; push it as WIP at least hourly. The coordinator lands.
- Never end a turn waiting: poll your own job's marker with a bounded wait.

**Ask the owner only for:** looks, gameplay-visible choices, outward posts, deletions. Everything else: do it.

**Hand back:** use playbook/templates/HANDBACK.md. Hand back early with a resume list if context runs long.
