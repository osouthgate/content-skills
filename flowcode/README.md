# flowcode

Run a task as a staged multi-agent workflow: look, build, review. A cheap model looks, a mid-tier model builds, and the strongest model reviews the real diff.

The skill is a thin router so it costs almost nothing on Claude Code and still works elsewhere.

| Host | What happens |
| --- | --- |
| Claude Code | `SKILL.md` is all it reads, and it is one sentence: use a dynamic workflow, haiku to look, sonnet to build, opus as the reviewer. |
| Codex, Cursor, Antigravity, others | `SKILL.md` sends the agent to `references/portable.md` (full procedure) and `references/packets.md` (templates). |

## Install

Claude Code:

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install flowcode@content-skills
```

Codex, Cursor or any host that loads `SKILL.md` folders: from the root of the `content-skills` repo, symlink the skill folder by absolute path into the host's skills folder, for example:

```bash
ln -s "$(pwd)/flowcode/skills/flowcode" ~/.codex/skills/flowcode
```

Use `~/.cursor/skills/` or `~/.agents/skills/` in place of `~/.codex/skills/` for those hosts.

## Use

```text
/flowcode migrate the billing module to the new client and keep the tests green
```

## What the portable route will not do

- Commit, push, publish or deploy unless you ask.
- Delete, force push or touch production data or credentials without one clear question first.
- Run more than one fix round after review without asking.

On Claude Code these come from Claude's own rules, not from this skill.

## Notes

- The skill sets `disable-model-invocation: true` (and `allow_implicit_invocation: false` for Codex), so it only runs when you call it. The `Workflow` tool is used only because you did.
