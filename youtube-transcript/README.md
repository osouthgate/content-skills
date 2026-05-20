# youtube-transcript

Extract YouTube transcripts and optionally summarize them.

This plugin keeps one canonical implementation:

```text
skills/youtube-transcript/scripts/yt_transcribe.py
```

The standalone CLI launcher in `bin/youtube-transcript` runs that same script, so the plugin and CLI do not drift.

## Claude Code install

```bash
claude plugin marketplace add osouthgate/content-skills
claude plugin install youtube-transcript@content-skills
```

## Session-only development

```bash
claude --plugin-dir ./youtube-transcript
```

## Standalone CLI

Install dependencies:

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Paste your OpenAI key into `.env` if you want summaries or audio transcription fallback:

```text
OPENAI_API_KEY=sk-...
```

Run the CLI:

```powershell
python .\bin\youtube-transcript "https://www.youtube.com/watch?v=AgQ4cwL5eOM" --captions-only
python .\bin\youtube-transcript "C:\Users\me\Downloads\talk.mp4"
python .\bin\youtube-transcript "https://www.youtube.com/watch?v=AgQ4cwL5eOM" --summary
python .\bin\youtube-transcript --file "C:\Users\me\Documents\video.transcript.md" --summary
```

Outputs default to `~/Documents/YouTube Transcripts`, not the repo checkout. Override with:

```powershell
python .\bin\youtube-transcript "https://www.youtube.com/watch?v=VIDEO_ID" --output-dir "C:\Users\me\Documents\Transcripts"
```
