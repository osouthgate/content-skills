# Content Skills

Reusable content workflow plugins for Claude Code and Codex.

## Marketplace

This repo exposes a Claude-compatible marketplace at:

```text
.claude-plugin/marketplace.json
```

Install from Claude Code:

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install youtube-transcript@content-skills
claude plugin install supergoal@content-skills
claude plugin install autonomous-run@content-skills
claude plugin install outcome@content-skills
```

## Plugins

- `youtube-transcript` - Extract YouTube captions/transcripts, summarize transcript files, and fall back to OpenAI audio transcription when captions are unavailable.
- `supergoal` - Plan and autonomously build a software task end-to-end under a single `/goal`, with retry, fix-spec recovery, per-phase memory writeback, and a final audit. Capability-aware: on Claude Code it fans independent phases out to parallel subagents and self-verifies end-to-end against any web/mobile/service surface; on Codex it runs the same plan sequentially. Cross-platform (PowerShell + POSIX helpers). Adapted for Windows from [supergoal](https://github.com/robzilla1738/supergoal) by Robert Courson (MIT; see `supergoal/NOTICE.md`).
- `autonomous-run` - Set the operating posture for a long unattended run on Claude Code: auto permissions, dynamic-workflow subagent fan-out, `/goal` or `/loop` persistence, cloud execution, and end-to-end self-verification. Detects which levers are available and hands off cleanly. Pairs with `supergoal` (which owns planning + phase execution); `autonomous-run` owns whether the session can run for hours without a human.
- `outcome` - Turn a requirement, idea, or transcript into ONE outcome doc per capability. Human decisions enter verbatim into a protected §0 TLDR a founder reads in 60 seconds (outcome line, rules mapped to acceptance-test IDs or UNTESTED, success signal); the agent derives invariants with boundaries, mechanism with commit-pinned file:line evidence, Given/When/Then acceptance, and build phases. Also reviews externally-authored docs against the framework rubric and arms `agreed` docs by committing acceptance rows as red tests first.

Each plugin owns one canonical skill folder under `skills/<skill-name>/`. Standalone CLI launchers should call into that skill resource folder rather than copy the implementation.
