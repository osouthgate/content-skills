---
name: podcast-transcript
description: Extract podcast transcripts from Spotify episode links, Apple Podcasts episode links, public RSS feeds, direct transcript/audio URLs, and local media; save clean Markdown and metadata, with optional summaries. Use when the user asks to transcribe, convert, caption, summarize, or save a podcast episode as Markdown. Do not use for music tracks or for downloading Spotify-hosted audio.
---

# Podcast Transcript

Use the bundled script for deterministic podcast resolution and transcription:

```bash
python3 scripts/podcast_transcribe.py "EPISODE_URL_OR_FILE"
```

## Source handling

- For a Spotify episode URL, treat Spotify only as an identifier. The script reads Spotify metadata, searches Apple's public podcast catalog for the same episode, and uses the publisher's public RSS feed or enclosure. It never downloads or records Spotify's stream.
- Prefer a publisher-supplied Podcasting 2.0 transcript from the RSS `<podcast:transcript>` tag. Convert VTT, SRT, JSON, HTML, Markdown, or plain text into a Markdown transcript without calling a model.
- When no published transcript exists, download the public RSS enclosure and transcribe chunked audio. The default `auto` mode prefers the local Ollama speech model, then falls back to OpenAI when an API key is configured.
- If automatic matching is missing or ambiguous, stop. Ask the user for the RSS feed, direct public audio URL, or local media rather than guessing.
- Spotify-exclusive episodes with no public source are unsupported.

## Common tasks

Spotify or Apple Podcasts episode:

```bash
python3 scripts/podcast_transcribe.py "https://open.spotify.com/episode/EPISODE_ID"
python3 scripts/podcast_transcribe.py "https://podcasts.apple.com/gb/podcast/show/id123?i=456"
```

RSS feed (use `--episode` unless the user wants the newest episode):

```bash
python3 scripts/podcast_transcribe.py "https://example.com/feed.xml" --episode "Episode title"
```

Override an unresolved Spotify match with a known publisher feed:

```bash
python3 scripts/podcast_transcribe.py "SPOTIFY_EPISODE_URL" --rss-url "https://example.com/feed.xml"
```

Resolve without downloading or transcribing:

```bash
python3 scripts/podcast_transcribe.py "EPISODE_URL" --resolve-only
```

Use only a published transcript, with no audio fallback:

```bash
python3 scripts/podcast_transcribe.py "EPISODE_URL" --published-only
```

Local audio and optional summary:

```bash
python3 scripts/podcast_transcribe.py "/path/to/episode.mp3" --summary
```

Force fully local audio transcription:

```bash
ollama pull gabegoodhart/granite4.1-speech:2b
python3 scripts/podcast_transcribe.py "EPISODE_URL_OR_FILE" --transcriber ollama
```

The Ollama path converts audio into 30-second, mono 16 kHz WAV chunks—the window size recommended by IBM's Granite Speech reference implementation—and uses `gabegoodhart/granite4.1-speech:2b` by default. Override the model with `--ollama-transcribe-model` or the window with `--chunk-seconds`. Use `--transcriber openai` for the hosted fallback; its default window is ten minutes. Ollama transcription is local, but resolving a Spotify link and downloading its publisher-hosted RSS audio still require internet access.

The default output directory is `~/Documents/Podcast Transcripts`. Use `--output-dir` when the user requests another location. Outputs are `.transcript.md`, `.metadata.json`, and, with `--summary`, `.summary.md`.

## Credentials

Load keys from a `.env` file in the current directory or the environment. `OPENAI_API_KEY` is required only when OpenAI performs audio transcription or summaries; local Ollama transcription needs no API key. Optional Spotify credentials (`SPOTIFY_ACCESS_TOKEN`, or `SPOTIFY_CLIENT_ID` plus `SPOTIFY_CLIENT_SECRET`) improve episode matching but are not required for basic oEmbed title resolution.

Do not put secrets in command arguments or output metadata. Do not summarize unless the user requests it.
