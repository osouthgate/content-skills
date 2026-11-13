---
name: worktree-cleanup
description: Review Git worktree disk usage and clean up finished checkouts. Use for worktree clean-up, stale agent checkouts, merged branch workspaces, or worktrees filling a disk. Runs a deterministic script, preserves branches and unfinished work, and applies only an explicitly approved saved plan. Not a general folder, Docker or cache cleaner.
argument-hint: "[repository paths]"
---

# Worktree clean-up

Use `scripts/worktree_cleanup.py` beside this file. Requires Python 3.10+, Git,
Linux `/proc`, and GNU `du`. GitHub PR checks also require authenticated `gh`.
No worktrunk, Python packages, network installers, or elevated permissions.

Resolve the directory containing this SKILL.md, following its installation
symlink. On Claude Code it is `${CLAUDE_SKILL_DIR}`. On other hosts use the
resolved skill directory. Set `SCRIPT` to its `scripts/worktree_cleanup.py`.
Never assume a fixed checkout or installation path.

## 1. Report

Use the repositories the user named; otherwise use the current Git repository.
Do not search every disk or discover unrelated projects. One invocation accepts
several repositories and deduplicates their common Git directories.

```bash
python3 "$SCRIPT" report /absolute/path/to/repo --github
```

For GitHub origins use `--github`: open PRs are kept, and exact merged PR heads
can prove squash/rebase integration. For other origins omit it: ancestry of the
current default branch is required. Missing tools, API failures, stale refs and
unknown merge evidence must produce KEEP or a refusal, never a fallback removal.
The script contacts origin to check freshness but does not fetch. If it reports
stale refs, fetch the intended origin, then rerun the report; do not weaken checks.

Summarise KEEP and REMOVE rows, sizes, and reasons. Main checkout sizes can
include nested worktrees; do not add overlapping rows or promise exact savings
on compressed/reflinked filesystems. These reports are local: do not commit them
or send their paths, branch names or private PR links elsewhere.

## 2. Prepare the selection

Choose only eligible REMOVE rows in the user's requested scope. The default
minimum age is two days. Explain any proposed age change first. Create a unique
plan file outside repositories, selecting each exact path:

```bash
python3 "$SCRIPT" plan /absolute/path/to/repo --github \
  --select /absolute/path/to/finished-checkout --output /tmp/worktree-plan-unique.json
```

Present the selected paths, sizes, integration evidence, and the ignored build
directories that will be discarded. Recommend one concrete selection. **Ask for
approval of this selection before applying it**, unless the user already approved
these exact paths and consequences in this conversation. A request to build or
install this skill is not permission to clean the machine. KEEP is never overridable
by changing a plan file or adding force flags: resolve the cause and scan again.

## 3. Apply and verify

```bash
python3 "$SCRIPT" apply /tmp/worktree-plan-unique.json --approve SHA256_FROM_PLAN_OUTPUT
```

The digest binds the saved plan, machine and user; it is not itself evidence of
user permission. Plans expire after one hour. A full selection preflight runs
before any removal, then each checkout is checked again. The script invokes
plain `git worktree remove`, never force, clean, stash, branch deletion or `rm -rf`.
It preserves local branches, including those retained after squash merges.

Report successful removals only after the script confirms them. If removal stops
partway, report both completed and refused entries; do not retry another route.
Check remaining registrations with `git worktree list` and filesystem space with
`df -h`. Do not silently prune missing registrations or remove leftover folders.

## Protected work

- Main, locked, recent, dirty, untracked, missing and symlinked checkouts stay.
- Ignored files stay unless they are entirely inside recognised build/cache
  directories: `node_modules`, `.next`, `.turbo`, `__pycache__`, `.pytest_cache`.
  In particular, an ignored `.env`, saved data or custom `scratch` folder blocks
  removal. Never print file contents to decide whether something is a secret.
- Submodules and Git operations in progress stay. Closed PRs, pushed branches and
  branch names alone do not prove integration. A merged PR must match HEAD exactly
  and target the default branch.
- Same-user Linux process cwd/open-file checks are best effort. They cannot see
  every process, remote agent or between-check race. Respect agent locks and the
  host's session/claim records. Have owners stop sessions or mark them with
  `git worktree lock` before choosing removals; never unlock another session.
- This script provides no guaranteed race-free deletion against concurrent edits.
  Do not run it on worktrees another session may still change.
