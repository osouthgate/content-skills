# Preventing the same disk growth

Read this only when disk usage will return, or when the user asks why it
returned. Mention the relevant pattern. Do not apply it. Cleanup stays on the
report, plan, and apply steps in `SKILL.md`, using `$SCRIPT`. Do not call a
repo-relative `disk-cleanup/skills/...` path.

## Hand off or stop

- Git worktrees are the large contributors: stop and use `worktree-cleanup`.
- Docker build cache, stopped containers, dangling images, or the pip / mise
  download caches in `SKILL.md` will refill: name the pattern below, then use
  this skill's plan for anything it can remove.
- Anything else: report the size and the human command in the table below, then
  stop. Those commands are outside this script. Do not call them disposable.

## Docker patterns to mention

Say these when writing or reviewing Dockerfiles, test runners, and compose
files. Do not edit the daemon, restart Docker, or delete volumes.

- Ephemeral containers: `docker run --rm` so an exited container does not keep
  its writable layer.
- Image layers: a BuildKit cache mount keeps package downloads out of the image.

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile
```

- Builder storage: this script reserves 10 GB of build cache when it prunes.
  A human GC cap has to sit above that reserve. One example is 15 GB in
  `/etc/docker/daemon.json`:

```json
{
  "builder": {
    "gc": {
      "enabled": true,
      "defaultKeepStorage": "15GB"
    }
  }
}
```

Changing that file and restarting Docker is a host change. Describe it. Do not
run it, and do not use sudo.

`docker compose down -v` deletes volumes. This skill does not. Mention it only
for a named test stack the user confirms is disposable, and still do not run it.
Never improvise `volume prune` or `system prune --volumes`.

## Report only

| What | How to see it | Human command, not this skill |
|---|---|---|
| Pacman cache | `du -sh /var/cache/pacman/pkg` | `paccache -rk2` |
| yay / AUR build files | `du -sh ~/.cache/yay` | `yay -Sc --aur` |
| npm cache | `du -sh ~/.npm` | `npm cache verify` |
| Core dumps | `coredumpctl list` | `coredumpctl vacuum --keep-index --until="3 days ago"` |
| Journal | `journalctl --disk-usage` | `sudo journalctl --vacuum-time=14d` |

pip and the mise download caches are in scope. Select them with this skill's
plan. Do not purge them with another command.
