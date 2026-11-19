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
claude plugin install podcast-transcript@content-skills
claude plugin install supergoal@content-skills
claude plugin install autonomous-run@content-skills
claude plugin install promise@content-skills
claude plugin install handoff-to-agent@content-skills
claude plugin install worktree-cleanup@content-skills
claude plugin install disk-cleanup@content-skills
claude plugin install ci-optimiser@content-skills
# then, inside a project:  /promise adopt
```

`promise` now lives in its own repository, [osouthgate/promise](https://github.com/osouthgate/promise). This marketplace still lists it, so `promise@content-skills` keeps working; new installs can use `claude plugin marketplace add osouthgate/promise` directly. Codex / Cursor: see [its README](https://github.com/osouthgate/promise#codex-and-other-hosts).

`handoff-to-agent` works on Claude, Cursor, and Codex — install via the marketplace on Claude, or symlink `handoff-to-agent/skills/handoff-to-agent` into `~/.cursor/skills/`, `~/.codex/skills/`, or `~/.agents/skills/` (see [its README](handoff-to-agent/README.md)). The other plugins are written primarily for Claude Code.

## Plugins

- `youtube-transcript` - Extract YouTube captions/transcripts, summarize transcript files, and fall back to OpenAI audio transcription when captions are unavailable.
- `podcast-transcript` - Extract podcast transcripts from Spotify episode links, Apple Podcasts episode links, public RSS feeds, direct transcript/audio URLs, and local media; save clean Markdown and metadata, with optional summaries. Spotify is used only as an episode identifier — audio always comes from the publisher's public RSS feed, never Spotify's stream.
- `supergoal` - Plan and autonomously build a software task end-to-end under a single `/goal`, with retry, fix-spec recovery, per-phase memory writeback, and a final audit. Capability-aware: on Claude Code it fans independent phases out to parallel subagents and self-verifies end-to-end against any web/mobile/service surface; on Codex it runs the same plan sequentially. Cross-platform (PowerShell + POSIX helpers). Adapted for Windows from [supergoal](https://github.com/robzilla1738/supergoal) by Robert Courson (MIT; see `supergoal/NOTICE.md`).
- `autonomous-run` - Set the operating posture for a long unattended run on Claude Code: auto permissions, dynamic-workflow subagent fan-out, `/goal` or `/loop` persistence, cloud execution, and end-to-end self-verification. Detects which levers are available and hands off cleanly. Pairs with `supergoal` (which owns planning + phase execution); `autonomous-run` owns whether the session can run for hours without a human.
- `promise` - Write the promise before the build, then prove it kept. You write the outcome and rules in your own words; the model may argue in notes but never rewrite them; your acceptance rows become failing tests before any code is written. Lives in [osouthgate/promise](https://github.com/osouthgate/promise).
- `handoff-to-agent` - Hand a session to another agent harness (`cursor`/`agent`, `claude`, `codex`, `agy`). Writes a self-contained handoff doc, prints a paste-ready first-move prompt, then asks before spawning the target in Herdr. See [`handoff-to-agent/README.md`](handoff-to-agent/README.md).
- `worktree-cleanup` - Review Git worktree sizes and integration evidence, then remove a reviewed selection. Also carries lifecycle prevention (one parent for new checkouts, end-of-task teardown, weekly report cadence). Keeps branches, unfinished work, protected ignored files and locked checkouts. Script and skill work on Claude, Codex and Cursor. See [`worktree-cleanup/README.md`](worktree-cleanup/README.md).
- `disk-cleanup` - Review disk and Docker usage; prepare approved clean-up plans for build cache, individual stopped containers/unused images and download caches. Docker volumes and saved application data remain protected. Script and skill work on Claude, Codex and Cursor. See [`disk-cleanup/README.md`](disk-cleanup/README.md).
- `ci-optimiser` - Measure GitHub Actions time with a run ledger (commit, PR, wall, queue, job and step times), find the biggest cost and the commit where a job changed speed, scan workflows for slow patterns, and make CI faster one measured change at a time. Never drops required checks, tests or security scans. Node 22.18+, no packages. See [`ci-optimiser/README.md`](ci-optimiser/README.md).

For why the same disk growth returns, start at [`STORAGE_OPTIMIZATION.md`](STORAGE_OPTIMIZATION.md). Each installed skill carries its own prevention note.

The `outcome` plugin was removed in promise 1.2.0; its framework lives on in `promise`. Everything `/outcome` did, `/promise` does, and `/promise adopt` sets a project up.

Each plugin owns one canonical skill folder under `skills/<skill-name>/`. Standalone CLI launchers should call into that skill resource folder rather than copy the implementation.

## License

MIT — see [LICENSE](./LICENSE). `supergoal` carries an additional notice in `supergoal/NOTICE.md`.
