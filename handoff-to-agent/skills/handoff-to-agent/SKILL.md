---
name: handoff-to-agent
description: |
  Cross-harness session handoff: summarize this session into a handoff
  document, print a paste-ready first-move prompt, then ask before spawning
  the target agent (cursor/agent, claude, codex, agy) in Herdr when available.
  Use when asked to "handoff to agent", "handoff to cursor/claude/codex/agy",
  "transfer to another harness", or "/handoff-to-agent".
  Not for same-session resume (use context-save / context-restore) or browser
  pairing (use pair-agent). Not the gstack /handoff inbox wrap.
argument-hint: "<cursor|claude|codex|agy|google> [title]"
---

# /handoff-to-agent — Cross-Harness Handoff

Package **this session** for another agent harness. Always write a handoff
file and a paste-ready prompt. **Never spawn until the user confirms.**

Self-contained: do not call gstack `/context-save` or `/handoff`.

## Resolve scripts dir

Scripts live next to this file:

```text
skills/handoff-to-agent/scripts/write_handoff.py
skills/handoff-to-agent/scripts/spawn_target.py
```

On Claude Code, `${CLAUDE_SKILL_DIR}` is this skill directory. On Cursor/Codex,
resolve `SKILL_DIR` as the directory containing this `SKILL.md` (symlink target
or checkout). Then:

```bash
SKILL_DIR="${CLAUDE_SKILL_DIR:-$SKILL_DIR}"
WRITE_PY="$SKILL_DIR/scripts/write_handoff.py"
SPAWN_PY="$SKILL_DIR/scripts/spawn_target.py"
```

---

## Step 0 — Parse args

User form: `/handoff-to-agent <target> [optional title…]`

| Arg | CLI |
|---|---|
| `cursor` | `agent` |
| `claude` | `claude` |
| `codex` | `codex` |
| `agy` / `google` | `agy` |

Validate with the script (unknown target exits non-zero and lists aliases):

```bash
python3 "$SPAWN_PY" --resolve "<target>"
```

If missing target, ask once. Do not guess.

---

## Step 1 — Gather (this session only)

1. Run a git snapshot:

```bash
python3 "$WRITE_PY" --git-snapshot --cwd "$(pwd)"
```

2. From conversation context (do **not** invent Linear/PR inbox noise), draft:

- **summary** — what we were doing (2–6 sentences)
- **decisions** — choices locked this session (bullets)
- **files** — paths touched or that matter next (bullets)
- **remaining** — ordered remaining work (bullets)
- **first_move** — 1–3 imperative sentences for the receiving agent

Scope: **this session only**. If something was not discussed or done here,
leave it out.

---

## Step 2 — Write the handoff file

Write a JSON payload to a temp file, then:

```bash
python3 "$WRITE_PY" \
  --target "<target>" \
  --cwd "$(pwd)" \
  --title "<optional title>" \
  --source-harness "<cursor|claude|codex|agy|unknown>" \
  --payload /tmp/handoff-payload.json
```

Payload shape:

```json
{
  "summary": "...",
  "decisions": ["...", "..."],
  "files": ["path/a", "path/b"],
  "remaining": ["1. ...", "2. ..."],
  "first_move": "..."
}
```

Capture `HANDOFF_FILE=...` from stdout. The file lands at:

```text
~/.local/share/handoffs/<repo-slug>/YYYYMMDD-HHMMSS-<target>.md
```

If write fails, stop and surface the error. Never modify project code.

---

## Step 3 — Print paste-ready prompt

Print a short status block, then **exactly one** fenced code block containing
the paste-ready prompt (use the `PASTE_PROMPT_BEGIN`…`END` region from the
script, or the Paste-ready section of the file).

**Never use markdown blockquotes (`>`)** for the paste region — they contaminate
copy/paste.

```
HANDOFF READY
════════════════════════════════════════
File:     <HANDOFF_FILE>
Target:   <canonical> (<cli>)
Branch:   <from snapshot>
════════════════════════════════════════
```

Then:

````
```
Read first: <absolute path>
Then: <first-move sentences>
Continue the work in <cwd>. Do not re-litigate decisions already listed.
```
````

---

## Step 4 — Ask before spawn

Ask explicitly (plain prose, one question):

> Spawn `<target>` (`<cli>`) in a new Herdr tab/terminal now?

- **No / not now** → stop. Leave the file path + paste block. Done.
- **Yes** → Step 5.

Do not spawn on silence. Do not auto-spawn.

Optional preview before asking:

```bash
python3 "$SPAWN_PY" --detect
python3 "$SPAWN_PY" --dry-run --target "<target>" --cwd "$(pwd)" \
  --prompt-file /tmp/handoff-prompt.txt
```

Write the paste-ready prompt text into `/tmp/handoff-prompt.txt` (or another
temp path) before dry-run / launch.

---

## Step 5 — Spawn (only after yes)

```bash
python3 "$SPAWN_PY" --launch --target "<target>" --cwd "$(pwd)" \
  --prompt-file /tmp/handoff-prompt.txt
```

Behavior (owned by the script):

1. Prefer `herdr-app do tab.new … --argv '["<cli>"]' --task "<prompt>"` when a
   Herdr window is usable.
2. Else `hc run --bg --outlive-parent --name handoff-<target> --cwd … <cli> "<prompt>"`.
3. Else fail soft: report that Herdr is unavailable and keep the paste block.

Interactive only — never `-p`, `codex exec`, or other headless one-shot modes.

On success: tell the user the method (`herdr-app` or `hc`), tab/terminal name,
and that they can steer the new agent.

On failure / `first_message.sent: false`: show the script JSON, suggest
`hc get <name>` / `hc read <name>`, and **do not blindly resend**. Point them
back at the paste-ready prompt.

---

## Rules

- **Never modify project source** — only write under `~/.local/share/handoffs/`.
- **Confirm before spawn** — always.
- **Fail soft** — missing git, missing CLI, missing Herdr: still deliver the doc
  + paste prompt when possible.
- **Not** gstack `/handoff`, `/context-save`, or `pair-agent`.
- **One target per invocation.**
