# YouTube Transcript Tool

Single-file CLI for extracting YouTube transcripts and optionally summarizing them.

## What it does

- Uses YouTube captions first for fast transcript extraction.
- Can run captions-only for long videos.
- Falls back to audio download plus OpenAI transcription when captions are missing.
- Summarizes YouTube transcripts or local transcript/text files with OpenAI by default.
- Supports Ollama summaries only when explicitly requested.

## Setup

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Then paste your OpenAI key into `.env`:

```text
OPENAI_API_KEY=sk-...
```

## Usage

Transcript only:

```powershell
python .\yt_transcribe.py "https://www.youtube.com/watch?v=AgQ4cwL5eOM"
```

Captions only:

```powershell
python .\yt_transcribe.py "https://www.youtube.com/watch?v=AgQ4cwL5eOM" --captions-only
```

Transcript plus OpenAI summary:

```powershell
python .\yt_transcribe.py "https://www.youtube.com/watch?v=AgQ4cwL5eOM" --summary
```

Summarize a local transcript or text file:

```powershell
python .\yt_transcribe.py --file ".\transcripts\video.transcript.md" --summary
```

Force audio transcription:

```powershell
python .\yt_transcribe.py "https://www.youtube.com/watch?v=VIDEO_ID" --audio-only
```

Outputs are written to `transcripts/` by default.
