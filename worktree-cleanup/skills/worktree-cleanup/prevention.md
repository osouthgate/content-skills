# Preventing the same worktree growth

Read this only when finished checkouts will accumulate again, or when the user
asks why they do. Mention the relevant pattern. Do not apply host maintenance
from here. Bulk removal stays on the report, plan, and apply steps in
`SKILL.md`, using `$SCRIPT`. Do not call a repo-relative
`worktree-cleanup/skills/...` path.

Docker, download caches, and other disk cleanup belong to `disk-cleanup`.

## Create under one parent

Agents often create a sibling directory next to the main checkout for every
ticket (`../my-repo-p1-1234`). That scatters multi-gigabyte trees across the
parent folder and makes review hard.

Prefer one parent per repository:

- Claude Code native worktrees: `<repo>/.claude/worktrees/<name>`
- Codex and other agents: `<repo-parent>/<repo-name>-worktrees/<name>`

Do not invent a third layout. Do not create loose `../<repo>-*` siblings beside
the main checkout when a parent directory already exists for that purpose.

## Tear down when the agent is done

Agents create a worktree per task and often leave it after the PR is open or
merged. A frontend checkout can hold a multi-gigabyte `node_modules`, plus its
own `.turbo` and `.next` trees, so the copies add up.

When the agent has finished with that checkout — PR opened and no further local
edits needed, or the task merged, closed, or abandoned — remove it from the
main repository:

```bash
git -C /absolute/path/to/main-repo worktree remove /absolute/path/to/finished-worktree
```

Never `rm -rf` a registered worktree. Branches stay; the remote branch and PR
are enough to recreate the checkout later. If `git worktree remove` refuses
(dirty tree, protected ignored files), report the exact blocker. Do not leave
silent orphans.

This end-of-task remove is separate from this skill's report. The skill keeps
open PRs, recent activity, and checkouts that contain ignored non-artifact
files (for example `.env`). Agents must still remove their own finished tree.

## Do not copy secrets into the worktree

An ignored `.env`, `.env.local`, or custom `scratch` folder blocks later
approved removal. Prefer Doppler, host environment, or the main checkout's env.
Do not copy secret files into a disposable worktree so the skill can clean it
up later.

## Weekly cadence

For repositories that spawn agent worktrees, run a weekly report with
`--github` when the origin is GitHub:

```bash
python3 "$SCRIPT" report /absolute/path/to/repo --github
python3 "$SCRIPT" report --discover /absolute/parent --github
```

`--discover` searches that directory for worktrees. It does not cross
filesystems or follow symlinks. Unregistered folders stay KEEP.

Summarise REMOVE candidates. Only plan and apply rows the skill marks REMOVE
and the user approves. Open PRs, recent trees, and secret-bearing checkouts
will KEEP — that is expected. Do not weaken age checks or force-remove to empty
the list.

## Share caches

Mention these when the same repositories keep large duplicate caches. Do not
rewrite a project's config unless the user asks for that change.

- Turborepo: set `TURBO_CACHE_DIR` to one directory outside the worktrees, such
  as `~/.cache/turbo`.
- Next.js: point each worktree's `.next/cache` at one shared directory with a
  symlink or that project's external cache setting. Leave the rest of `.next`
  per checkout.

On btrfs, a person can deduplicate copies of named dependency trees with
`duperemove`. Do not run it, and do not invent paths for it.
