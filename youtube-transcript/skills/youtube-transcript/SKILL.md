---
name: youtube-transcript
description: Extract transcripts from YouTube videos, local audio/video files, and summarize transcript files. Use when the user asks to download, fetch, extract, transcribe, caption, or summarize a YouTube video, a YouTube URL, a video ID, a local media file such as .mp4/.mov/.mp3/.m4a/.wav, or an existing transcript/text file. Supports captions-only, chunked local media transcription through OpenAI, YouTube audio fallback through OpenAI, and summaries through OpenAI or opt-in Ollama.
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
- Write `.transcript.md` and `.metadata.json` into `~/Documents/YouTube Transcripts`.
- Do not summarize unless `--summary` is supplied.
- Use `--output-dir "path\to\folder"` when the user asks for a specific output folder. Prefer a user data folder, not a git repo checkout.

For local audio/video files, pass the file path directly. The script extracts audio with ffmpeg, using bundled `imageio-ffmpeg` if no system ffmpeg is installed, chunks it, and transcribes each chunk with OpenAI.

## Common Tasks

Captions only, no audio fallback:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --captions-only
```

Custom output folder:

```powershell
python scripts\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir "C:\Users\me\Documents\Transcripts"
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

Transcribe a local video or audio file:

```powershell
python scripts\yt_transcribe.py "C:\Users\me\Downloads\talk.mp4"
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
- The script self-installs missing Python packages with `pip install --upgrade`: `youtube-transcript-api`, `yt-dlp`, `openai`, `requests`, and `imageio-ffmpeg`.
- For large transcripts, OpenAI summaries are chunked automatically.
