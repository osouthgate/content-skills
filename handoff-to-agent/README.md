# handoff-to-agent

Cross-harness session handoff for Claude Code, Cursor, Codex, and AGY.

Writes a handoff document (goal, decisions, remaining work, first move), prints a
paste-ready first-move prompt, then **asks before** spawning the target agent in
Herdr when available.

```text
/handoff-to-agent cursor
/handoff-to-agent claude "finish auth middleware"
/handoff-to-agent agy
/handoff-to-agent google   # alias for agy
/handoff-to-agent codex
```

Not the same as gstack `/handoff` (same-person next-session wrap) or
`/context-save` / `/context-restore`. This skill transfers work **to another
agent harness**.

## Install

### Claude Code

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install handoff-to-agent@content-skills
```

Session-only from a checkout:

```bash
claude --plugin-dir /path/to/content-skills/handoff-to-agent
```

### Cursor / Codex / other hosts

Symlink the skill folder (one source of truth):

```bash
ln -s /path/to/content-skills/handoff-to-agent/skills/handoff-to-agent \
  ~/.cursor/skills/handoff-to-agent

# optional also:
ln -s /path/to/content-skills/handoff-to-agent/skills/handoff-to-agent \
  ~/.agents/skills/handoff-to-agent
```

## Targets

| Arg | CLI launched |
|---|---|
| `cursor` | `agent` |
| `claude` | `claude` |
| `codex` | `codex` |
| `agy` / `google` | `agy` |

## What it writes

```text
~/.local/share/handoffs/<repo-slug>/YYYYMMDD-HHMMSS-<target>.md
```

## Herdr spawn (after you confirm)

1. Prefer `herdr-app do tab.new … --task "…"` when the window is available.
2. Else `hc run --bg --outlive-parent … <cli> "…"`.
3. Else fail soft: keep the paste-ready prompt for manual paste.

Interactive only — never headless `-p` / `exec` modes.

## Scripts

```bash
# Git snapshot only (JSON on stdout)
python3 skills/handoff-to-agent/scripts/write_handoff.py --git-snapshot

# Write a handoff file from a JSON payload
python3 skills/handoff-to-agent/scripts/write_handoff.py \
  --target cursor --payload /tmp/handoff-payload.json

# Detect Herdr / resolve target (no launch)
python3 skills/handoff-to-agent/scripts/spawn_target.py --detect
python3 skills/handoff-to-agent/scripts/spawn_target.py --resolve cursor

# Launch (skill asks the human first)
python3 skills/handoff-to-agent/scripts/spawn_target.py \
  --target cursor --cwd /path/to/repo --prompt-file /tmp/prompt.txt
```
