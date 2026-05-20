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
```

## Plugins

- `youtube-transcript` - Extract YouTube captions/transcripts, summarize transcript files, and fall back to OpenAI audio transcription when captions are unavailable.

Each plugin owns one canonical skill folder under `skills/<skill-name>/`. Standalone CLI launchers should call into that skill resource folder rather than copy the implementation.
