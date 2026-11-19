---
name: disk-cleanup
description: Review disk space, Docker build cache, stopped containers, unused images and download caches. Use for disk full alerts, Docker clean-up, reclaimable Docker space, cache clean-up or storage reviews. Runs a script with read-only reports and approved saved plans. Preserves Docker volumes, running services, app profiles, models, databases and personal files. Worktree removal belongs to worktree-cleanup.
argument-hint: "[folders to inspect]"
---

# Disk and Docker clean-up

Use `scripts/disk_cleanup.py` beside this file. Requires Python 3.10+, Linux,
GNU `df`/`du`, and Docker CLI for Docker operations (current Buildx for build cache). No Python dependencies,
elevated permissions, system configuration changes or scheduled jobs.

Resolve the directory containing this SKILL.md, following installation symlinks.
Claude Code provides `${CLAUDE_SKILL_DIR}`; other hosts use the resolved skill
directory. Set `SCRIPT` to its `scripts/disk_cleanup.py`.

## 1. Inspect first

```bash
python3 "$SCRIPT" report
python3 "$SCRIPT" report --scan /absolute/path/to/local/folder
```

Add `--skip-docker` when Docker is irrelevant. Repeat `--scan` only for explicit
local folders in the requested scope. Never scan remote/cloud mounts or recurse
through the entire home directory by default. Reports inspect file metadata, not
document or secret contents. Do not commit or publish machine reports/plans.

Explain which filesystem is filling, available bytes and largest contributors.
RAM-backed `/tmp` and a disk are separate capacities. Compressed/reflinked folders,
Docker shared layers and snapshots prevent additive totals or exact promises.
If permissions hide snapshots or system storage, say what remains unverified;
do not elevate or change filesystem settings.

Docker targets are pinned to an explicit local context and daemon identity.
Remote endpoints and `DOCKER_HOST` overrides are refused; do not switch to another
daemon as a workaround. Missing Docker does not block the filesystem report.

## 2. Prepare a narrow plan

Start with rebuildable caches. Supported actions:

| Selection | What it does |
|---|---|
| `--build-cache` | Prune unused cache in the local context's built-in Docker builder, using the reviewed age policy with an extra one-hour margin, and reserve 10 GB of cache. Rebuilds may take longer. |
| `--container FULL_ID` | Remove this old exited/dead container, including its writable layer. Preserve its volumes. Restart-managed containers are refused. |
| `--image FULL_SHA256_ID` | Remove this old untagged, undigested image if no container references it. |
| `--cache pip` | Delete individually recorded old files in `~/.cache/pip`. |
| `--cache mise-downloads` / `mise-cas` | Delete individually recorded old tool downloads in the corresponding mise cache. |

Flags may repeat for several IDs/caches. The default minimum age is seven days;
`--min-age-days` supports one day or more. Do not reduce it without explaining
the changed selection. Stop package downloads/installs before selecting their
cache files; recent mtime checks alone cannot prove a file is idle.

```bash
python3 "$SCRIPT" plan --build-cache --cache pip --output /tmp/disk-plan-unique.json
```

The plan stores unchanged file identities or exact Docker object IDs. It never
stores shell commands. Review the actual plan, including selected container
names/writable-layer consequences and all cache roots. Recommend a concrete
selection with the expected benefit and rebuild cost. **Ask for approval of that
selection before applying**, unless these exact actions have already been
approved in the conversation. Building/installing the skill authorises no live
clean-up. Do all investigation and plan preparation before asking.

Docker's CLI has no exact build-cache prune preview. A build-cache plan approves
the displayed builder, age and storage policy, not a frozen list of cache
IDs or a promised byte count. State this limit when presenting it. It does not
cover Buildx custom builders. Buildx accepts a duration: the script recomputes
the age from the reviewed cutoff and adds one hour to err toward keeping files.
Only a single-node `docker` driver at the approved local endpoint is supported.

## 3. Apply and verify

```bash
python3 "$SCRIPT" apply /tmp/disk-plan-unique.json --approve SHA256_FROM_PLAN_OUTPUT
```

The digest binds the reviewed plan, machine and user; it does not replace user
permission. Plans expire after an hour. The script preflights every selected item
before changing anything, then rechecks each action. Cache files must remain
unchanged single-link regular files; parent directories are opened without
following symlinks. Docker targets, stopped states and image usage are rechecked.
No forced container/image removal, volume flags or general system prune.

Report only confirmed actions. On failure, report partial completion and the
refusal; do not retry a broader command. Recheck `df -h` and the relevant Docker
usage. Empty cache directories are intentionally left in place.

## When the same growth will return

After verify, name what will refill the disk. Read [prevention.md](prevention.md)
only in that case, or when the user asks why usage returns. On a normal cleanup,
do not open it and do not apply it.

- Git worktrees dominate: stop and use `worktree-cleanup`.
- Docker build cache will refill: tell the user about `docker run --rm`,
  BuildKit cache mounts, and a builder GC cap above this script's 10 GB reserve.
  Do not edit `daemon.json`, restart Docker, or delete volumes.
- Pacman, journal, yay, npm, or other system caches dominate: report the size
  and the usual human command from prevention.md, then stop. Do not run them.

## Always preserve

- Docker volumes (named or anonymous), even when Docker calls them unused or
  reclaimable. They can contain the only copy of a database. **No volume deletion
  is implemented.** A request to remove one requires a separately reviewed data
  procedure; never improvise `volume prune` or `system prune --volumes`.
- Running, paused, created, restarting and restart-managed containers; all
  services, networks, tagged/digest-pinned images and images referenced by any
  container. Container removal can still discard saved writable-layer data:
  users must review exact containers, not approve a blanket stopped-container sweep.
- App profiles/workspaces, model stores, documents, Dropbox/Drive files, personal
  or project data, swap files and snapshots. Arbitrary directory deletion, `/tmp`
  sweeps, system-package caches, npm/pnpm pruning and yay build-source deletion
  are outside this script. Report them when relevant; do not call them disposable.
- Keep the host's existing permissions and production rules. Do not stop jobs,
  run sudo, install timers, change mount settings, or prune production Docker.
