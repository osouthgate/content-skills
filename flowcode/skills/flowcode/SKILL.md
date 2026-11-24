---
name: flowcode
description: Run a task as a staged multi-agent workflow with a cheap-to-strong model ladder and an independent reviewer. On Claude Code it is one instruction (a dynamic workflow, haiku to look, sonnet to build, opus to review). On Codex, Cursor and other hosts it routes to fuller step-by-step instructions. Use only when the user invokes flowcode or explicitly asks for a dynamic workflow, a multi-agent workflow, parallel agents, or a swarm.
argument-hint: "[task]"
disable-model-invocation: true
---

# flowcode

**If you are Claude Code:**

> Use a dynamic workflow to get this done: haiku to look things up, sonnet to build, opus as the reviewer.

Then stop reading. Do the task.

**If you are anything else** (Codex, Cursor, Antigravity, a plain chat model, or any host without Claude Code's `Workflow` or `Agent` tool): read [references/portable.md](references/portable.md) and follow it.
