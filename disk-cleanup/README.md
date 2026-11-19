# Disk and Docker clean-up

Review filesystem usage, Docker and explicitly selected local folders. Prepare
a saved clean-up plan for old Docker build cache, individual stopped containers,
individual dangling images, or allowlisted download-cache files.

## Install

```bash
claude plugin install disk-cleanup@content-skills
```

For Codex, Cursor or another skill host, link or copy the canonical
[`skills/disk-cleanup`](skills/disk-cleanup) directory into `~/.agents/skills/`,
`~/.codex/skills/` or `~/.cursor/skills/`. Invoke `disk-cleanup` for disk or Docker
clean-up. Read the full [SKILL.md](skills/disk-cleanup/SKILL.md) before using it.

## CLI

Python 3.10+, Linux and GNU coreutils; Docker CLI for Docker actions, and current
Buildx with `--reserved-space` for build-cache clean-up. No Python packages.

```bash
python3 /path/to/disk-cleanup/skills/disk-cleanup/scripts/disk_cleanup.py report --scan /path/to/local/folder
python3 /path/to/disk-cleanup/skills/disk-cleanup/scripts/disk_cleanup.py plan --build-cache --cache pip --output /tmp/reviewed-disk-plan.json
python3 /path/to/disk-cleanup/skills/disk-cleanup/scripts/disk_cleanup.py apply /tmp/reviewed-disk-plan.json --approve PLAN_SHA256
```

`report` makes no deletions; `plan` only writes a new private JSON file. Apply
requires its SHA256, machine/user identity, a plan less than one hour old and
current eligibility checks. Keep private inventories outside source control.

Other plan selections: `--container FULL_ID`, `--image FULL_SHA256_ID`,
`--cache mise-downloads`, `--cache mise-cas`. Defaults to files/objects at least
seven days old; `--min-age-days` has a one-day floor. No default blanket selection.
Cache removal records and rechecks each unchanged file. It preserves symlinks,
hardlinks, new/changed files and empty directories. Pause package installs first.

Docker uses a pinned local context (`--context NAME`). `DOCKER_HOST` must be unset.
Only the selected context's built-in, single-node `docker` builder is supported;
selected/custom/remote builders cannot redirect the command. Build-cache plans
approve a scope (unused, reviewed age policy, 10 GB reserved cache); Docker offers no
exact dry-run list. Other Docker removals use full IDs without force. Removing a
stopped container discards its writable layer; its volumes remain.

Buildx needs a duration rather than an absolute cutoff. At apply, the script
recomputes age from the plan's cutoff and adds one hour to err toward keeping.

**Volumes are report-only.** No volume, network, system-wide or remote Docker
prune is implemented. Neither are app data, models, arbitrary folders, `/tmp`
sweeps, swap, snapshots, system-package caches or production operations. Folder
and Docker totals are not additive, and are not guaranteed recoverable space.

## Tests and references

```bash
python3 -m unittest discover -s tests -v
```

Tests use disposable cache files and a fake Docker command layer. They do not
delete real Docker objects. Live validation uses reports and command help only.

- [Prevention notes](skills/disk-cleanup/prevention.md) (installed with the skill; the repo index is [STORAGE_OPTIMIZATION.md](../STORAGE_OPTIMIZATION.md))
- [Docker Buildx prune](https://docs.docker.com/reference/cli/docker/buildx/prune/)
- [Docker Buildx builder inspection](https://docs.docker.com/reference/cli/docker/buildx/inspect/)
- [Docker container removal](https://docs.docker.com/reference/cli/docker/container/rm/)
- [Docker image removal](https://docs.docker.com/reference/cli/docker/image/rm/)
- [Why broad Docker system pruning differs](https://docs.docker.com/reference/cli/docker/system/prune/)
