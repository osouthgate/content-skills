# podcast-transcript

Extract podcast transcripts from Spotify episode links, Apple Podcasts episode links, public RSS feeds, direct transcript/audio URLs, and local media.

This plugin keeps one canonical implementation:

```text
skills/podcast-transcript/scripts/podcast_transcribe.py
```

The standalone CLI launcher in `bin/podcast-transcript` runs that same script, so the plugin and CLI do not drift.

Spotify is used only as an episode identifier: the script reads Spotify metadata, matches the episode against Apple's public podcast catalog, and pulls audio/transcript from the publisher's public RSS feed. It never downloads or records Spotify's stream, and Spotify-exclusive episodes with no public source are unsupported.

## Claude Code install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install podcast-transcript@content-skills
```

## Session-only development

```bash
claude --plugin-dir ./podcast-transcript
```

## Standalone CLI

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Paste your OpenAI key into `.env` if you want OpenAI-based audio transcription or summaries. Spotify credentials are optional and only improve episode matching:

```text
OPENAI_API_KEY=sk-...
SPOTIFY_ACCESS_TOKEN=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

Run the CLI:

```bash
./bin/podcast-transcript "https://open.spotify.com/episode/EPISODE_ID"
./bin/podcast-transcript "https://podcasts.apple.com/gb/podcast/show/id123?i=456"
./bin/podcast-transcript "https://example.com/feed.xml" --episode "Episode title"
./bin/podcast-transcript "/path/to/episode.mp3" --summary
```

Outputs default to `~/Documents/Podcast Transcripts`, not the repo checkout. Override with:

```bash
./bin/podcast-transcript "EPISODE_URL" --output-dir "/path/to/transcripts"
```

The default `auto` transcriber prefers a local Ollama speech model (`gabegoodhart/granite4.1-speech:2b`) and falls back to OpenAI when configured. Force one or the other with `--transcriber ollama` or `--transcriber openai`.
