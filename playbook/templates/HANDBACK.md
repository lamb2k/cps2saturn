# Hand-back: lane/<name>, <date>

**Result:** <one line, the point first: what works now, at which tier>

## Commits

| Hash | Subject |
| --- | --- |
| <hash> | <subject> |

Branch `lane/<name>` at <hash>, pushed: <yes/no>. Dirty files left: <none / list>.
Base used: <commit or work folder, and how you know it is the right one>.

State: implemented <yes, pushed / no> / tested <tier> / accepted <no, needs owner look / owner, date> /
released <no / version>.

## Proven

| Claim | Tier | Evidence |
| --- | --- | --- |
| <claim> | HOST / MAME / EMULATOR / MODELLED / ASSUMED / HARDWARE | <log, still or hash, path> |

Image: <file> sha256 <hash>, build flags <flags>, emulator copy and settings <name, patches, profile>.

Runs per figure: <n; three for anything that decides a default, with the spread>.
Controls: <for each A/B or gate, the evidence that both arms played the same scene, and the check that can fail>.
Budget line: <row, gain expected in the brief, gain measured>.

## Premises checked

- <each premise of the brief: held / wrong, and what was measured>

## Staging and assists

- <anything that helped the run or the capture: health held, memory writes, settings changed, frames cut; or none>
- <anything you inferred rather than were told, and why>

## Changed from the brief

- <scope you changed, and why; or none>

## Not proven

- <what was not run, and why>

## Blockers

- <exact error text, command to reproduce>

## Resume list

1. <next step, with the command>
2. <...>

## Housekeeping

- Intermediate images deleted: <yes, manifest path / no, why>
- Processes left running: <none, checked by pid against the lane's log / pid, command and the time it ends>
- Traps found, and where they were written down: <lane rules section / none>
