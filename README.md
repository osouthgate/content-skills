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

The `outcome` plugin was removed in promise 1.2.0; its framework lives on in `promise`. Everything `/outcome` did, `/promise` does, and `/promise adopt` sets a project up.

Each plugin owns one canonical skill folder under `skills/<skill-name>/`. Standalone CLI launchers should call into that skill resource folder rather than copy the implementation.

## License

MIT — see [LICENSE](./LICENSE). `supergoal` carries an additional notice in `supergoal/NOTICE.md`.
