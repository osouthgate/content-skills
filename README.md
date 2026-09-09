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
claude plugin install promise@content-skills
```

## Plugins

- `youtube-transcript` - Extract YouTube captions/transcripts, summarize transcript files, and fall back to OpenAI audio transcription when captions are unavailable.
- `supergoal` - Plan and autonomously build a software task end-to-end under a single `/goal`, with retry, fix-spec recovery, per-phase memory writeback, and a final audit. Capability-aware: on Claude Code it fans independent phases out to parallel subagents and self-verifies end-to-end against any web/mobile/service surface; on Codex it runs the same plan sequentially. Cross-platform (PowerShell + POSIX helpers). Adapted for Windows from [supergoal](https://github.com/robzilla1738/supergoal) by Robert Courson (MIT; see `supergoal/NOTICE.md`).
- `autonomous-run` - Set the operating posture for a long unattended run on Claude Code: auto permissions, dynamic-workflow subagent fan-out, `/goal` or `/loop` persistence, cloud execution, and end-to-end self-verification. Detects which levers are available and hands off cleanly. Pairs with `supergoal` (which owns planning + phase execution); `autonomous-run` owns whether the session can run for hours without a human.
- `outcome` - **Superseded by `promise`; kept for one release.** Turn a requirement, idea, or transcript into ONE outcome doc per capability. Human decisions enter verbatim into a protected §0 TLDR a founder reads in 60 seconds (outcome line, rules mapped to acceptance-test IDs or UNTESTED, success signal); the agent derives invariants with boundaries, mechanism with commit-pinned file:line evidence, Given/When/Then acceptance, and build phases. Also reviews externally-authored docs against the framework rubric and arms `agreed` docs by committing acceptance rows as red tests first.
- `promise` - Carry a capability from intent to proof in one skill: the Outcome Framework doc first (protected §0 TLDR: outcome line, verbatim rules mapped to acceptance-row ids, success signal), then the agent half; where a project keeps a capability map, `arm` files the rows and commits red tests, `intake` routes feedback onto existing promises, and `reconcile` moves a verdict only at the altitude the row's own Then claims. Seven modes behind one router, Python scripts, per-project config. Supersedes `outcome`.

Each plugin owns one canonical skill folder under `skills/<skill-name>/`. Standalone CLI launchers should call into that skill resource folder rather than copy the implementation.
