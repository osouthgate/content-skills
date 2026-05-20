---
name: youtube-transcript
description: Extract transcripts from YouTube videos and summarize transcript files. Use when the user asks to download, fetch, extract, transcribe, caption, or summarize a YouTube video, a YouTube URL, a video ID, or an existing transcript/text file. Supports captions-only, audio transcription fallback through OpenAI, and summaries through OpenAI or opt-in Ollama.
---

# YouTube Transcript

Use the bundled script for deterministic transcript work instead of recreating the workflow.

## Quick Start

Run from the skill directory or call the script by absolute path:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Default behavior for YouTube input:

- Try YouTube captions first with `youtube-transcript-api`.
- If captions fail, download audio with `yt-dlp` and transcribe with OpenAI.
- Write `.transcript.md` and `.metadata.json` into `transcripts/`.
- Do not summarize unless `--summary` is supplied.

## Common Tasks

Captions only, no audio fallback:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --captions-only
```

Transcript plus OpenAI summary:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --summary
```

Summarize an existing transcript/text file:

```powershell
python scripts\yt_transcribe.py --file "path\to\transcript.md" --summary
```

Force audio transcription:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --audio-only
```

## API Keys

Prefer a `.env` file in the current working directory:

```text
OPENAI_API_KEY=sk-...
```

The script also accepts `OPENAI_API_KEY`, `OPENAI_KEY`, `OPENAI_API_TOKEN`, or `--openai-api-key`. Avoid putting keys in shell history unless the user explicitly chooses that.

## Notes

- Use `--captions-only` for long videos when the user wants the fast/simple path.
- OpenAI is the default summarizer. Use `--summarizer ollama` only when the user explicitly wants local Ollama.
- The script self-installs missing Python packages with `pip install --upgrade`: `youtube-transcript-api`, `yt-dlp`, `openai`, and `requests`.
- For large transcripts, OpenAI summaries are chunked automatically.
