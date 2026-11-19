# Worktree clean-up

A small skill around a Python script. Reports first; removes an explicitly
selected, reviewed plan. Keeps branches, local changes, protected ignored files,
locked worktrees and checkouts without current integration evidence. The
installed [prevention.md](skills/worktree-cleanup/prevention.md) covers
lifecycle prevention: one parent directory for new checkouts, end-of-task
teardown, no secret copies into disposable trees, and a weekly report cadence.

## Install

Claude Code, with the content-skills marketplace configured:

```bash
claude plugin install worktree-cleanup@content-skills
```

For Codex, Cursor or another skill host, link or copy the canonical
[`skills/worktree-cleanup`](skills/worktree-cleanup) directory into that host's
skill directory (`~/.agents/skills/`, `~/.codex/skills/` or `~/.cursor/skills/`).
Then ask for `worktree-cleanup` and name the repositories.

## CLI

Python 3.10+, Git, Linux `/proc` and GNU `du`; optional authenticated GitHub CLI.
Run from any directory:

```bash
python3 /path/to/worktree-cleanup/skills/worktree-cleanup/scripts/worktree_cleanup.py report /path/to/repo --github
python3 /path/to/worktree-cleanup/skills/worktree-cleanup/scripts/worktree_hunt.py /absolute/root
python3 /path/to/worktree-cleanup/skills/worktree-cleanup/scripts/worktree_cleanup.py report --discover /absolute/root --github
python3 /path/to/worktree-cleanup/skills/worktree-cleanup/scripts/worktree_cleanup.py plan /path/to/repo --github --select /path/to/finished-checkout --output /tmp/reviewed-worktrees.json
python3 /path/to/worktree-cleanup/skills/worktree-cleanup/scripts/worktree_cleanup.py apply /tmp/reviewed-worktrees.json --approve PLAN_SHA256
```

`worktree_hunt.py` only searches the absolute roots it is given. It does not
follow symlinks or cross onto another filesystem, and it does not delete
anything. `--discover` passes those roots to it, then reports the repositories
it found. Checkouts that are no longer registered stay KEEP.

JSON reports include reasons and approximate directory bytes. Origin's default
tracking branch must match the remote. Fetch before retrying a stale-ref refusal.
The default activity threshold is two days (`--min-age-days`). Plans expire after
an hour and are tied to the machine, user, path inode, HEAD and reviewed evidence.
GitHub API errors refuse eligibility. No remote is also a refusal.

Only known ignored build directories are allowed; other ignored files block
removal. Successful removal also discards those recognised ignored build
directories. All local branches remain. There is no force option. Missing
registrations, submodules and leftover folders require separate review.

Process checks are best effort and cannot eliminate concurrent-edit races.
Stop other sessions or use Git worktree locks. The script never stops processes.
The complete procedure and limits are in [SKILL.md](skills/worktree-cleanup/SKILL.md).

## Tests and implementation

From the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Tests create disposable Git repositories and never touch live worktrees.
This implementation is original, building on the conservative design of the
local worktree reaper. The [reviewed gist](https://gist.github.com/Seklfreak/209374b10a4a12582b9917f16a6bf8c9)
inspired the workflow, but none of its source is copied. It does not require
worktrunk, auto-stash dirty files, delete branches or sweep sibling directories.

Reference: [Git worktree documentation](https://git-scm.com/docs/git-worktree). Prevention notes installed with the skill: [prevention.md](skills/worktree-cleanup/prevention.md). Repo index: [STORAGE_OPTIMIZATION.md](../STORAGE_OPTIMIZATION.md).
