#!/usr/bin/env python3
"""
Single-file YouTube transcript helper.

Fast path: fetch existing YouTube captions with youtube-transcript-api.
Fallback: download audio with yt-dlp and transcribe it with OpenAI.
Optional: summarize with local Ollama or OpenAI.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from getpass import getpass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


DEPENDENCIES = {
    "youtube_transcript_api": "youtube-transcript-api",
    "yt_dlp": "yt-dlp",
    "openai": "openai",
    "requests": "requests",
    "imageio_ffmpeg": "imageio-ffmpeg",
}

MEDIA_SUFFIXES = {
    ".aac",
    ".flac",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".wav",
    ".webm",
}


def ensure_module(import_name: str) -> Any:
    try:
        return importlib.import_module(import_name)
    except ImportError:
        package_name = DEPENDENCIES[import_name]
        print(f"Installing missing dependency: {package_name}", file=sys.stderr, flush=True)
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", package_name]
        )
        return importlib.import_module(import_name)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_openai_api_key(cli_key: str | None, interactive: bool = False) -> str | None:
    candidates = (
        cli_key,
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_KEY"),
        os.getenv("OPENAI_API_TOKEN"),
    )
    for key in candidates:
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key

    if interactive and sys.stdin.isatty():
        key = getpass("OpenAI API key: ").strip()
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    return None


def video_id_from(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    path = parsed.path.strip("/")

    if "youtu.be" in host and path:
        return path.split("/")[0]

    if "youtube.com" in host:
        query_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_id:
            return query_id
        parts = path.split("/")
        for marker in ("shorts", "embed", "live"):
            if marker in parts and parts.index(marker) + 1 < len(parts):
                return parts[parts.index(marker) + 1]

    match = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", value)
    if match:
        return match.group(1)

    raise ValueError("Could not find an 11-character YouTube video ID in that input.")


def sanitize_filename(value: str, fallback: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]', " ", value).strip()
    safe = re.sub(r"\s+", " ", safe)
    return (safe[:120] or fallback).rstrip(". ")


def output_basename_for_file(path: Path) -> str:
    stem = path.stem
    for suffix in (".transcript", ".summary", ".metadata"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return sanitize_filename(stem, fallback="transcript")


def default_output_dir() -> Path:
    return Path.home() / "Documents" / "YouTube Transcripts"


def resolve_output_dir(value: str) -> Path:
    return Path(value).expanduser().resolve()


def timestamp(seconds: float) -> str:
    seconds = max(0, float(seconds))
    whole = int(seconds)
    return str(dt.timedelta(seconds=whole))


def snippets_from_fetched(fetched: Any) -> list[dict[str, Any]]:
    if hasattr(fetched, "to_raw_data"):
        raw = fetched.to_raw_data()
        if isinstance(raw, list):
            return raw

    snippets = getattr(fetched, "snippets", fetched)
    normalized = []
    for item in snippets:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append(
                {
                    "text": getattr(item, "text", ""),
                    "start": getattr(item, "start", 0),
                    "duration": getattr(item, "duration", 0),
                }
            )
    return normalized


def transcript_text(snippets: list[dict[str, Any]], include_timestamps: bool) -> str:
    lines = []
    previous = None
    for item in snippets:
        text = " ".join(str(item.get("text", "")).replace("\n", " ").split())
        if not text:
            continue
        start = float(item.get("start", 0) or 0)
        if include_timestamps:
            lines.append(f"[{timestamp(start)}] {text}")
        elif text != previous:
            lines.append(text)
        previous = text
    return "\n".join(lines).strip()


def fetch_youtube_caption(video_id: str, languages: list[str]) -> tuple[str, dict[str, Any]]:
    yta = ensure_module("youtube_transcript_api")
    api = yta.YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=languages, preserve_formatting=False)
    snippets = snippets_from_fetched(fetched)
    meta = {
        "source": "youtube_captions",
        "language": getattr(fetched, "language", None),
        "language_code": getattr(fetched, "language_code", None),
        "is_generated": getattr(fetched, "is_generated", None),
        "snippet_count": len(snippets),
    }
    return transcript_text(snippets, include_timestamps=True), meta


def get_video_info(url: str) -> dict[str, Any]:
    yt_dlp = ensure_module("yt_dlp")
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(url, download=False)


def download_audio(url: str, work_dir: Path) -> Path:
    yt_dlp = ensure_module("yt_dlp")
    output_template = str(work_dir / "%(id)s.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = Path(ydl.prepare_filename(info))
    if not filename.exists():
        matches = list(work_dir.glob(f"{info.get('id', '*')}.*"))
        if matches:
            return matches[0]
    return filename


def transcribe_with_openai(
    audio_path: Path, model: str, api_key: str | None, ask_for_key: bool
) -> str:
    api_key = resolve_openai_api_key(api_key, interactive=ask_for_key)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set, so audio fallback transcription cannot run."
        )
    openai = ensure_module("openai")
    client = openai.OpenAI(api_key=api_key)
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            response_format="text",
        )
    return str(result).strip()


def ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    imageio_ffmpeg = ensure_module("imageio_ffmpeg")
    return str(imageio_ffmpeg.get_ffmpeg_exe())


def split_media_to_audio_chunks(media_path: Path, work_dir: Path, chunk_seconds: int) -> list[Path]:
    chunk_pattern = str(work_dir / "chunk_%04d.mp3")
    command = [
        ffmpeg_executable(),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "32k",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        chunk_pattern,
    ]
    subprocess.run(command, check=True)
    chunks = sorted(work_dir.glob("chunk_*.mp3"))
    if not chunks:
        raise RuntimeError(f"Could not extract audio chunks from {media_path}")
    return chunks


def transcribe_local_media(
    media_path: Path,
    model: str,
    api_key: str | None,
    ask_for_key: bool,
    chunk_seconds: int,
) -> str:
    with tempfile.TemporaryDirectory(prefix="local-media-transcribe-") as temp_dir:
        chunks = split_media_to_audio_chunks(media_path, Path(temp_dir), chunk_seconds)
        parts = []
        for index, chunk in enumerate(chunks, start=1):
            print(f"Transcribing chunk {index}/{len(chunks)}...", file=sys.stderr)
            text = transcribe_with_openai(chunk, model, api_key, ask_for_key)
            if text:
                parts.append(f"<!-- chunk {index}/{len(chunks)} -->\n\n{text}")
        return "\n\n".join(parts).strip()


def resolve_ollama_model(model: str, host: str) -> str:
    requests = ensure_module("requests")
    if model != "auto":
        return model

    response = requests.get(f"{host.rstrip('/')}/api/tags", timeout=20)
    response.raise_for_status()
    model_items = response.json().get("models", [])
    models = [item for item in model_items if item.get("name")]
    if not models:
        raise RuntimeError(
            "Ollama is running, but no local models were found. Pull one first, "
            "for example: ollama pull llama3.1"
        )

    def score(item: dict[str, Any]) -> tuple[int, int]:
        name = item["name"].lower()
        details = item.get("details") or {}
        family = str(details.get("family") or "").lower()
        families = " ".join(str(part).lower() for part in details.get("families") or [])
        text = f"{name} {family} {families}"
        coding_penalty = 1 if any(word in text for word in ("coder", "code", "devstral")) else 0
        return coding_penalty, int(item.get("size") or 0)

    return sorted(models, key=score)[0]["name"]


def summarize_with_ollama(text: str, model: str, host: str) -> tuple[str, str]:
    requests = ensure_module("requests")
    resolved_model = resolve_ollama_model(model, host)
    prompt = (
        "Summarize this transcript in a useful, concise way. Include key points, "
        "decisions, action items, and notable quotes when present.\n\n"
        f"Transcript:\n{text}"
    )
    response = requests.post(
        f"{host.rstrip('/')}/api/chat",
        json={
            "model": resolved_model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("message", {}).get("content", "").strip(), resolved_model


def summarize_with_openai(
    text: str, model: str, api_key: str | None, ask_for_key: bool
) -> str:
    api_key = resolve_openai_api_key(api_key, interactive=ask_for_key)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set, so OpenAI summarization cannot run.")
    openai = ensure_module("openai")
    client = openai.OpenAI(api_key=api_key)

    chunks = split_text(text, max_chars=60_000)
    if len(chunks) > 1:
        partials = []
        for index, chunk in enumerate(chunks, start=1):
            print(f"Summarizing chunk {index}/{len(chunks)} with OpenAI...", file=sys.stderr)
            partials.append(
                summarize_with_openai_text(
                    client,
                    model,
                    chunk,
                    instruction=(
                        "Summarize this transcript chunk. Preserve concrete facts, "
                        "important arguments, timestamps if helpful, and action items."
                    ),
                )
            )
        return summarize_with_openai_text(
            client,
            model,
            "\n\n".join(f"Chunk {i + 1} summary:\n{summary}" for i, summary in enumerate(partials)),
            instruction=(
                "Combine these chunk summaries into one coherent final summary. "
                "Return sections for overview, key points, action items, and notable quotes."
            ),
        )

    return summarize_with_openai_text(
        client,
        model,
        text,
        instruction=(
            "You summarize transcripts clearly. Return sections for summary, "
            "key points, action items, and notable quotes if any."
        ),
    )


def split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current: list[str] = []
    current_size = 0
    for line in text.splitlines():
        line_size = len(line) + 1
        if current and current_size + line_size > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += line_size
    if current:
        chunks.append("\n".join(current))
    return chunks


def summarize_with_openai_text(client: Any, model: str, text: str, instruction: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": instruction,
            },
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content.strip()


def write_outputs(
    output_dir: Path,
    basename: str,
    transcript: str,
    metadata: dict[str, Any],
    summary: str | None,
) -> tuple[Path, Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{basename}.transcript.md"
    metadata_path = output_dir / f"{basename}.metadata.json"
    summary_path = output_dir / f"{basename}.summary.md" if summary else None

    transcript_path.write_text(transcript + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if summary_path and summary:
        summary_path.write_text(summary + "\n", encoding="utf-8")

    return transcript_path, metadata_path, summary_path


def summarize_transcript(
    transcript: str,
    args: argparse.Namespace,
    metadata: dict[str, Any],
) -> str:
    print(f"Summarizing with {args.summarizer}...", file=sys.stderr)
    if args.summarizer == "ollama":
        summary, resolved_model = summarize_with_ollama(
            transcript, args.ollama_model, args.ollama_host
        )
        metadata["summary_model"] = f"ollama:{resolved_model}"
        return summary

    summary = summarize_with_openai(
        transcript,
        args.openai_summary_model,
        args.openai_api_key,
        args.ask_openai_key,
    )
    metadata["summary_model"] = f"openai:{args.openai_summary_model}"
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Paste a YouTube URL/ID to get a transcript, or pass a local text file "
            "to summarize it."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="YouTube URL/video ID, or a local transcript/text file. If omitted, prompts.",
    )
    parser.add_argument(
        "--file",
        dest="file",
        default=None,
        help="Read transcript text from this local file instead of YouTube.",
    )
    parser.add_argument("--summary", action="store_true", help="Also create a summary.")
    parser.add_argument(
        "--transcribe-only",
        action="store_true",
        help="Only create the transcript/metadata files. This is the default for YouTube input.",
    )
    parser.add_argument(
        "--summarizer",
        choices=["ollama", "openai"],
        default="openai",
        help="Summary backend. Defaults to OpenAI to avoid local Ollama memory pressure.",
    )
    parser.add_argument(
        "--ollama-model",
        default="auto",
        help="Ollama model for summaries, or 'auto' to pick a local model.",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama host URL.",
    )
    parser.add_argument(
        "--openai-summary-model",
        default="gpt-4o-mini",
        help="OpenAI chat model for summaries.",
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key. Prefer a .env file or OPENAI_API_KEY so it does not land in shell history.",
    )
    parser.add_argument(
        "--ask-openai-key",
        action="store_true",
        help="Prompt for an OpenAI API key when one is not found in the environment or .env.",
    )
    parser.add_argument(
        "--openai-transcribe-model",
        default="whisper-1",
        help="OpenAI audio transcription model.",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=600,
        help="Seconds per local audio/video chunk for OpenAI transcription.",
    )
    parser.add_argument(
        "--languages",
        default="en,en-GB,en-US",
        help="Comma-separated caption language priority list.",
    )
    parser.add_argument(
        "--force-audio",
        "--audio-only",
        dest="force_audio",
        action="store_true",
        help="Skip YouTube captions and transcribe downloaded audio with OpenAI.",
    )
    parser.add_argument(
        "--captions-only",
        action="store_true",
        help="Use YouTube captions only. Do not download audio or call OpenAI transcription if captions fail.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir()),
        help=(
            "Directory for transcript, metadata, and optional summary files. "
            f"Defaults to {default_output_dir()}."
        ),
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(Path(".env"))
    args = parse_args()
    if args.transcribe_only:
        args.summary = False

    output_dir = resolve_output_dir(args.output_dir)
    raw_input = args.file or args.input or input("Paste YouTube URL, ID, or file path: ").strip()
    source_path = Path(raw_input).expanduser()

    if source_path.exists() and source_path.suffix.lower() in MEDIA_SUFFIXES:
        transcript = transcribe_local_media(
            source_path,
            args.openai_transcribe_model,
            args.openai_api_key,
            args.ask_openai_key,
            args.chunk_seconds,
        )
        basename = output_basename_for_file(source_path)
        metadata: dict[str, Any] = {
            "source": "local_media_openai_audio_transcription",
            "input_file": str(source_path.resolve()),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "openai_transcribe_model": args.openai_transcribe_model,
            "chunk_seconds": args.chunk_seconds,
            "character_count": len(transcript),
        }
        transcript_path, metadata_path, _ = write_outputs(
            output_dir, basename, transcript, metadata, None
        )
        print(f"Transcript: {transcript_path.resolve()}")
        print(f"Metadata:   {metadata_path.resolve()}")

        if not args.summary:
            return 0

        try:
            summary = summarize_transcript(transcript, args, metadata)
        except Exception as exc:
            metadata["summary_error"] = f"{type(exc).__name__}: {exc}"
            write_outputs(output_dir, basename, transcript, metadata, None)
            print(f"Summary failed: {metadata['summary_error']}", file=sys.stderr)
            return 1

        _, _, summary_path = write_outputs(output_dir, basename, transcript, metadata, summary)
        if summary_path:
            print(f"Summary:    {summary_path.resolve()}")
        return 0

    if args.file or source_path.exists():
        transcript = source_path.read_text(encoding="utf-8")
        basename = output_basename_for_file(source_path)
        metadata: dict[str, Any] = {
            "source": "local_file",
            "input_file": str(source_path.resolve()),
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "character_count": len(transcript),
        }
        transcript_path, metadata_path, _ = write_outputs(
            output_dir, basename, transcript, metadata, None
        )
        print(f"Transcript: {transcript_path.resolve()}")
        print(f"Metadata:   {metadata_path.resolve()}")

        if not args.summary:
            print(
                "Local file loaded. Add --summary to summarize it.",
                file=sys.stderr,
            )
            return 0

        try:
            summary = summarize_transcript(transcript, args, metadata)
        except Exception as exc:
            metadata["summary_error"] = f"{type(exc).__name__}: {exc}"
            write_outputs(output_dir, basename, transcript, metadata, None)
            print(f"Summary failed: {metadata['summary_error']}", file=sys.stderr)
            print(
                "Tip: put OPENAI_API_KEY=sk-... in a .env file here, or set the "
                "OPENAI_API_KEY environment variable.",
                file=sys.stderr,
            )
            return 1

        _, _, summary_path = write_outputs(
            output_dir, basename, transcript, metadata, summary
        )
        if summary_path:
            print(f"Summary:    {summary_path.resolve()}")
        return 0

    url = raw_input
    video_id = video_id_from(url)
    full_url = url if urlparse(url).scheme else f"https://www.youtube.com/watch?v={video_id}"
    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]

    title = video_id
    metadata: dict[str, Any] = {
        "video_id": video_id,
        "url": full_url,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }

    transcript = ""
    caption_error = None
    if not args.force_audio:
        try:
            print("Trying YouTube captions...", file=sys.stderr)
            transcript, caption_meta = fetch_youtube_caption(video_id, languages)
            metadata.update(caption_meta)
        except Exception as exc:
            caption_error = f"{type(exc).__name__}: {exc}"
            print(f"Caption fetch failed: {caption_error}", file=sys.stderr)

    if not transcript:
        if args.captions_only:
            print("Captions-only mode requested, and no captions were fetched.", file=sys.stderr)
            return 1
        print("Downloading audio and transcribing with OpenAI...", file=sys.stderr)
        with tempfile.TemporaryDirectory(prefix="yt-transcribe-") as temp_dir:
            audio_path = download_audio(full_url, Path(temp_dir))
            transcript = transcribe_with_openai(
                audio_path,
                args.openai_transcribe_model,
                args.openai_api_key,
                args.ask_openai_key,
            )
        metadata.update(
            {
                "source": "openai_audio_transcription",
                "openai_transcribe_model": args.openai_transcribe_model,
            }
        )
        if caption_error:
            metadata["caption_error"] = caption_error

    try:
        info = get_video_info(full_url)
        title = info.get("title") or title
        metadata.update(
            {
                "title": title,
                "channel": info.get("channel") or info.get("uploader"),
                "duration": info.get("duration"),
                "webpage_url": info.get("webpage_url"),
            }
        )
    except Exception as exc:
        metadata["video_info_error"] = f"{type(exc).__name__}: {exc}"

    basename = sanitize_filename(f"{video_id} {title}", fallback=video_id)
    transcript_path, metadata_path, _ = write_outputs(
        output_dir, basename, transcript, metadata, None
    )
    print(f"Transcript: {transcript_path.resolve()}")
    print(f"Metadata:   {metadata_path.resolve()}")

    summary = None
    if args.summary:
        try:
            summary = summarize_transcript(transcript, args, metadata)
        except Exception as exc:
            metadata["summary_error"] = f"{type(exc).__name__}: {exc}"
            write_outputs(output_dir, basename, transcript, metadata, None)
            print(f"Summary failed: {metadata['summary_error']}", file=sys.stderr)
            print(
                "Tip: put OPENAI_API_KEY=sk-... in a .env file here, or set the "
                "OPENAI_API_KEY environment variable.",
                file=sys.stderr,
            )
            return 1

    if summary:
        transcript_path, metadata_path, summary_path = write_outputs(
            output_dir, basename, transcript, metadata, summary
        )
        if summary_path:
            print(f"Summary:    {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
