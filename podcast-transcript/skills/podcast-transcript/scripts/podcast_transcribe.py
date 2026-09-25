#!/usr/bin/env python3
"""Resolve public podcast sources and write Markdown transcripts.

Spotify is used only as an episode identifier. Audio is obtained from a
publisher's public RSS enclosure or from a source explicitly supplied by the
user; this script never downloads or records Spotify streams.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import difflib
import html
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from getpass import getpass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


DEPENDENCIES = {
    "imageio_ffmpeg": "imageio-ffmpeg",
    "openai": "openai",
}

MEDIA_SUFFIXES = {
    ".aac", ".flac", ".m4a", ".m4b", ".mkv", ".mov", ".mp3", ".mp4",
    ".mpeg", ".mpga", ".oga", ".ogg", ".opus", ".wav", ".webm",
}
TRANSCRIPT_SUFFIXES = {".html", ".htm", ".json", ".md", ".srt", ".txt", ".vtt"}
PODCAST_TRANSCRIPT_NAMESPACE = "https://podcastindex.org/namespace/1.0"
USER_AGENT = "podcast-transcript-skill/1.0 (+https://github.com/osouthgate/content-skills)"


class ResolutionError(RuntimeError):
    """Raised when an episode cannot be matched to a public source safely."""


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


def http_bytes(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
    max_bytes: int = 25 * 1024 * 1024,
) -> tuple[bytes, str, str]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request_headers.update(headers or {})
    request = Request(url, data=data, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise RuntimeError(f"Response exceeded {max_bytes // (1024 * 1024)} MB: {url}")
            return payload, response.headers.get_content_type(), response.geturl()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not fetch {url}: {exc.reason}") from exc


def http_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> Any:
    payload, _, _ = http_bytes(
        url,
        data=data,
        headers={"Accept": "application/json", **(headers or {})},
        timeout=timeout,
    )
    return json.loads(payload.decode("utf-8-sig"))


def download_file(url: str, destination: Path, max_bytes: int) -> tuple[Path, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "audio/*,*/*;q=0.8"})
    try:
        with urlopen(request, timeout=60) as response, destination.open("wb") as output:
            content_type = response.headers.get_content_type()
            total = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise RuntimeError(
                        f"Audio exceeded the configured {max_bytes // (1024 * 1024)} MB limit"
                    )
                output.write(block)
            return destination, content_type
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} while downloading public podcast audio") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not download public podcast audio: {exc.reason}") from exc


def spotify_episode_id(value: str) -> str:
    value = value.strip()
    uri_match = re.fullmatch(r"spotify:episode:([A-Za-z0-9]+)", value)
    if uri_match:
        return uri_match.group(1)
    parsed = urlparse(value)
    if parsed.netloc.lower() in {"open.spotify.com", "play.spotify.com"}:
        parts = [part for part in parsed.path.split("/") if part]
        if "episode" in parts and parts.index("episode") + 1 < len(parts):
            episode_id = parts[parts.index("episode") + 1]
            if re.fullmatch(r"[A-Za-z0-9]+", episode_id):
                return episode_id
    raise ValueError("Input is not a Spotify episode URL or URI.")


def canonical_spotify_url(value: str) -> str:
    return f"https://open.spotify.com/episode/{spotify_episode_id(value)}"


def apple_episode_id(value: str) -> str:
    parsed = urlparse(value)
    if "podcasts.apple.com" not in parsed.netloc.lower():
        raise ValueError("Input is not an Apple Podcasts URL.")
    episode_id = parse_qs(parsed.query).get("i", [""])[0]
    if not episode_id.isdigit():
        raise ValueError("Apple Podcasts URL does not contain an episode id in its i= parameter.")
    return episode_id


def is_spotify_episode(value: str) -> bool:
    try:
        spotify_episode_id(value)
        return True
    except ValueError:
        return False


def is_apple_episode(value: str) -> bool:
    try:
        apple_episode_id(value)
        return True
    except ValueError:
        return False


def fetch_spotify_access_token() -> str | None:
    direct = os.getenv("SPOTIFY_ACCESS_TOKEN", "").strip()
    if direct:
        return direct
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    result = http_json(
        "https://accounts.spotify.com/api/token",
        data=urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    return str(result.get("access_token") or "") or None


def spotify_metadata(value: str) -> dict[str, Any]:
    episode_id = spotify_episode_id(value)
    spotify_url = canonical_spotify_url(value)
    oembed = http_json(
        "https://open.spotify.com/oembed?" + urlencode({"url": spotify_url})
    )
    metadata: dict[str, Any] = {
        "source_platform": "spotify",
        "source_url": spotify_url,
        "episode_id": episode_id,
        "title": str(oembed.get("title") or episode_id),
        "artwork_url": oembed.get("thumbnail_url"),
    }
    try:
        embed_payload, _, _ = http_bytes(
            f"https://open.spotify.com/embed/episode/{quote(episode_id)}",
            max_bytes=5 * 1024 * 1024,
        )
        embed_html = embed_payload.decode("utf-8", errors="replace")
        next_data_match = re.search(
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            embed_html,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if next_data_match:
            next_data = json.loads(next_data_match.group(1))
            entity = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("state", {})
                .get("data", {})
                .get("entity", {})
            )
            release = entity.get("releaseDate") or {}
            metadata.update(
                {
                    "title": entity.get("title") or entity.get("name") or metadata["title"],
                    "podcast": entity.get("subtitle") or metadata.get("podcast"),
                    "duration_ms": entity.get("duration") or metadata.get("duration_ms"),
                    "release_date": release.get("isoString") or metadata.get("release_date"),
                }
            )
    except Exception as exc:
        metadata["spotify_embed_warning"] = f"{type(exc).__name__}: {exc}"
    try:
        token = fetch_spotify_access_token()
        if not token:
            return metadata
        api = http_json(
            f"https://api.spotify.com/v1/episodes/{quote(episode_id)}",
            headers={"Authorization": f"Bearer {token}"},
        )
        show = api.get("show") or {}
        metadata.update(
            {
                "title": api.get("name") or metadata["title"],
                "podcast": show.get("name"),
                "publisher": show.get("publisher"),
                "description": api.get("description"),
                "duration_ms": api.get("duration_ms"),
                "release_date": api.get("release_date"),
                "languages": api.get("languages"),
            }
        )
    except Exception as exc:
        metadata["spotify_metadata_warning"] = f"{type(exc).__name__}: {exc}"
    return metadata


def apple_lookup_episode(value: str, country: str) -> dict[str, Any]:
    episode_id = apple_episode_id(value)
    result = http_json(
        "https://itunes.apple.com/lookup?"
        + urlencode({"id": episode_id, "entity": "podcastEpisode", "country": country})
    )
    candidates = [item for item in result.get("results", []) if item.get("episodeUrl")]
    if not candidates:
        raise ResolutionError("Apple Podcasts did not return a public episode enclosure.")
    return candidates[0]


def normalized_title(value: str) -> str:
    value = html.unescape(str(value or "")).casefold()
    value = re.sub(r"^\s*#?\d+\s*[:.\-–—]\s*", "", value)
    value = re.sub(r"\b(?:episode|ep)\s*#?\s*(\d+)\b", r" \1 ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def similarity(left: str | None, right: str | None) -> float:
    a = normalized_title(left or "")
    b = normalized_title(right or "")
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def candidate_score(expected: dict[str, Any], candidate: dict[str, Any]) -> float:
    components: list[tuple[float, float]] = [
        (0.72, similarity(expected.get("title"), candidate.get("trackName")))
    ]
    if expected.get("podcast"):
        components.append(
            (0.16, similarity(expected.get("podcast"), candidate.get("collectionName")))
        )
    if expected.get("duration_ms") and candidate.get("trackTimeMillis"):
        difference = abs(int(expected["duration_ms"]) - int(candidate["trackTimeMillis"]))
        duration_score = max(0.0, 1.0 - difference / 300_000)
        components.append((0.08, duration_score))
    if expected.get("release_date") and candidate.get("releaseDate"):
        same_day = str(candidate["releaseDate"])[:10] == str(expected["release_date"])[:10]
        components.append((0.04, 1.0 if same_day else 0.0))
    total_weight = sum(weight for weight, _ in components)
    return sum(weight * score for weight, score in components) / total_weight


def apple_search_candidates(
    title: str, country: str, podcast_name: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    queries = [title]
    if podcast_name:
        queries.insert(0, f"{title} {podcast_name}")
    candidates: list[dict[str, Any]] = []
    for query in queries:
        result = http_json(
            "https://itunes.apple.com/search?"
            + urlencode(
                {
                    "term": query,
                    "media": "podcast",
                    "entity": "podcastEpisode",
                    "limit": limit,
                    "country": country,
                }
            )
        )
        candidates.extend(
            item for item in result.get("results", []) if item.get("episodeUrl")
        )
    return candidates


def choose_apple_candidate(
    expected: dict[str, Any], country: str, minimum_score: float
) -> tuple[dict[str, Any], float]:
    candidates = apple_search_candidates(
        str(expected.get("title") or ""),
        country,
        str(expected.get("podcast") or "") or None,
    )
    deduplicated: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            str(candidate.get("episodeUrl") or ""),
            normalized_title(candidate.get("trackName") or ""),
        )
        deduplicated[key] = candidate
    ranked = sorted(
        ((candidate_score(expected, candidate), candidate) for candidate in deduplicated.values()),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < minimum_score:
        best = ranked[0][0] if ranked else 0.0
        raise ResolutionError(
            "No sufficiently confident public podcast match was found for the Spotify "
            f"episode (best score {best:.3f}, required {minimum_score:.3f}). "
            "Supply --rss-url or --audio-url if you know the publisher's public source."
        )
    if len(ranked) > 1:
        first_score, first = ranked[0]
        second_score, second = ranked[1]
        if (
            first_score - second_score < 0.02
            and first.get("episodeUrl") != second.get("episodeUrl")
        ):
            raise ResolutionError(
                "The Spotify episode matched multiple public episodes equally well. "
                "Supply --rss-url or --audio-url rather than allowing a guess."
            )
    return ranked[0][1], ranked[0][0]


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def element_text(element: ET.Element, child_name: str) -> str:
    for child in element:
        if local_name(child.tag) == child_name and child.text:
            return child.text.strip()
    return ""


def parse_feed(payload: bytes, feed_url: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ResolutionError(f"The supplied URL is not valid podcast XML: {exc}") from exc
    show_title = ""
    for element in root.iter():
        if local_name(element.tag) in {"channel", "feed"}:
            show_title = element_text(element, "title")
            if show_title:
                break
    episodes: list[dict[str, Any]] = []
    for item in root.iter():
        if local_name(item.tag) not in {"item", "entry"}:
            continue
        title = element_text(item, "title")
        if not title:
            continue
        episode: dict[str, Any] = {
            "title": title,
            "podcast": show_title,
            "guid": element_text(item, "guid") or element_text(item, "id"),
            "release_date": (
                element_text(item, "pubdate")
                or element_text(item, "published")
                or element_text(item, "updated")
            ),
            "duration": element_text(item, "duration"),
            "audio_url": None,
            "transcripts": [],
        }
        for child in item.iter():
            name = local_name(child.tag)
            if name == "transcript":
                transcript_url = child.attrib.get("url") or child.attrib.get("href")
                if transcript_url:
                    episode["transcripts"].append(
                        {
                            "url": urljoin(feed_url, transcript_url),
                            "type": child.attrib.get("type") or "",
                            "language": child.attrib.get("language") or "",
                            "rel": child.attrib.get("rel") or "",
                        }
                    )
            elif name == "enclosure" and child.attrib.get("url"):
                media_type = child.attrib.get("type", "")
                if not episode["audio_url"] and (
                    not media_type or media_type.startswith("audio/")
                ):
                    episode["audio_url"] = urljoin(feed_url, child.attrib["url"])
            elif name == "link" and child.attrib.get("rel") == "enclosure":
                href = child.attrib.get("href")
                media_type = child.attrib.get("type", "")
                if href and not episode["audio_url"] and (
                    not media_type or media_type.startswith("audio/")
                ):
                    episode["audio_url"] = urljoin(feed_url, href)
        episodes.append(episode)
    if not episodes:
        raise ResolutionError("No podcast episodes were found in the supplied RSS/Atom feed.")
    return show_title, episodes


def fetch_feed(feed_url: str) -> tuple[str, list[dict[str, Any]], str]:
    payload, _, final_url = http_bytes(
        feed_url,
        headers={"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
        max_bytes=50 * 1024 * 1024,
    )
    show_title, episodes = parse_feed(payload, final_url)
    return show_title, episodes, final_url


def choose_feed_episode(
    episodes: list[dict[str, Any]],
    expected: dict[str, Any] | None,
    explicit_title: str | None,
) -> tuple[dict[str, Any], float]:
    title = explicit_title or str((expected or {}).get("title") or "")
    guid = str((expected or {}).get("guid") or "")
    if guid:
        for episode in episodes:
            if str(episode.get("guid") or "") == guid:
                return episode, 1.0
    if not title:
        return episodes[0], 1.0
    ranked = sorted(
        ((similarity(title, episode.get("title")), episode) for episode in episodes),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 0.72:
        raise ResolutionError(
            f"The feed did not contain a confident match for episode title {title!r}."
        )
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.01:
        if normalized_title(ranked[0][1]["title"]) != normalized_title(
            ranked[1][1]["title"]
        ):
            raise ResolutionError(
                "Multiple feed episodes matched the requested title. Pass a more exact --episode value."
            )
    return ranked[0][1], ranked[0][0]


def public_metadata_from_apple(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": candidate.get("trackName"),
        "podcast": candidate.get("collectionName"),
        "guid": candidate.get("episodeGuid"),
        "release_date": candidate.get("releaseDate"),
        "duration_ms": candidate.get("trackTimeMillis"),
        "description": candidate.get("description"),
        "feed_url": candidate.get("feedUrl"),
        "audio_url": candidate.get("episodeUrl"),
        "apple_episode_url": candidate.get("trackViewUrl"),
        "apple_episode_id": candidate.get("trackId"),
    }


def resolve_from_feed(
    feed_url: str,
    expected: dict[str, Any] | None,
    explicit_title: str | None,
) -> dict[str, Any]:
    show_title, episodes, final_url = fetch_feed(feed_url)
    episode, score = choose_feed_episode(episodes, expected, explicit_title)
    return {
        **(expected or {}),
        **episode,
        "podcast": episode.get("podcast") or show_title or (expected or {}).get("podcast"),
        "feed_url": final_url,
        "feed_match_score": round(score, 4),
    }


def resolve_episode(raw_input: str, args: argparse.Namespace) -> dict[str, Any]:
    if is_spotify_episode(raw_input):
        metadata = spotify_metadata(raw_input)
        if args.episode:
            metadata["title"] = args.episode
        if args.audio_url:
            return {**metadata, "audio_url": args.audio_url, "resolver": "explicit_audio"}
        if args.rss_url:
            result = resolve_from_feed(args.rss_url, metadata, args.episode)
            result["resolver"] = "explicit_rss"
            return result
        candidate, score = choose_apple_candidate(metadata, args.country, args.min_match_score)
        public = public_metadata_from_apple(candidate)
        combined = {**metadata, **{k: v for k, v in public.items() if v is not None}}
        combined["catalog_match_score"] = round(score, 4)
        combined["resolver"] = "spotify_oembed_to_apple_catalog"
        if public.get("feed_url"):
            try:
                feed_result = resolve_from_feed(str(public["feed_url"]), combined, args.episode)
                return {**combined, **feed_result}
            except Exception as exc:
                combined["feed_warning"] = f"{type(exc).__name__}: {exc}"
        return combined

    if is_apple_episode(raw_input):
        candidate = apple_lookup_episode(raw_input, args.country)
        metadata = {
            "source_platform": "apple_podcasts",
            "source_url": raw_input,
            **public_metadata_from_apple(candidate),
            "resolver": "apple_catalog_lookup",
        }
        if args.audio_url:
            metadata["audio_url"] = args.audio_url
            metadata["resolver"] = "explicit_audio"
            return metadata
        feed_url = args.rss_url or metadata.get("feed_url")
        if feed_url:
            try:
                return {
                    **metadata,
                    **resolve_from_feed(str(feed_url), metadata, args.episode),
                }
            except Exception as exc:
                metadata["feed_warning"] = f"{type(exc).__name__}: {exc}"
        return metadata

    if args.rss_url:
        result = resolve_from_feed(args.rss_url, {"source_url": raw_input}, args.episode)
        result["resolver"] = "explicit_rss"
        return result

    parsed = urlparse(raw_input)
    suffix = Path(parsed.path).suffix.lower()
    if parsed.scheme in {"http", "https"} and suffix in TRANSCRIPT_SUFFIXES:
        return {
            "title": args.episode or Path(parsed.path).stem or "podcast transcript",
            "source_url": raw_input,
            "transcripts": [{"url": raw_input, "type": "", "language": "", "rel": ""}],
            "resolver": "direct_transcript",
        }
    if args.audio_url:
        return {
            "title": args.episode or "podcast episode",
            "source_url": raw_input,
            "audio_url": args.audio_url,
            "resolver": "explicit_audio",
        }
    if parsed.scheme in {"http", "https"} and suffix in MEDIA_SUFFIXES:
        return {
            "title": args.episode or Path(parsed.path).stem or "podcast episode",
            "source_url": raw_input,
            "audio_url": raw_input,
            "resolver": "direct_audio",
        }
    if parsed.scheme in {"http", "https"}:
        result = resolve_from_feed(raw_input, None, args.episode)
        result["source_url"] = raw_input
        result["resolver"] = "rss_or_atom"
        return result
    raise ResolutionError(
        "Unsupported input. Use a Spotify/Apple episode URL, RSS feed, public transcript/audio URL, or local file."
    )


class TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n\n".join(line for line in lines if line)


def caption_timestamp(value: str) -> str:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        seconds = float(parts[-1])
        minutes = int(parts[-2]) if len(parts) >= 2 else 0
        hours = int(parts[-3]) if len(parts) >= 3 else 0
    except (ValueError, IndexError):
        return value
    whole = hours * 3600 + minutes * 60 + int(seconds)
    return str(dt.timedelta(seconds=whole))


def strip_caption_markup(value: str) -> str:
    value = html.unescape(value)
    speaker = ""
    match = re.match(r"\s*<v(?:\.\w+)?\s+([^>]+)>", value, flags=re.IGNORECASE)
    if match:
        speaker = match.group(1).strip() + ": "
        value = value[match.end():]
    value = re.sub(r"<[^>]+>", "", value)
    return speaker + " ".join(value.split())


def caption_blocks_to_markdown(raw: str, include_timestamps: bool) -> str:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalized)
    lines: list[str] = []
    for block in blocks:
        parts = [part.strip("\ufeff ") for part in block.splitlines() if part.strip()]
        if not parts or parts[0].upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        if len(parts) >= 2 and re.fullmatch(r"\d+", parts[0]):
            parts = parts[1:]
        timing_index = next((i for i, part in enumerate(parts) if "-->" in part), -1)
        if timing_index < 0:
            continue
        start = parts[timing_index].split("-->", 1)[0].strip()
        text = strip_caption_markup(" ".join(parts[timing_index + 1:]))
        if not text:
            continue
        lines.append(f"[{caption_timestamp(start)}] {text}" if include_timestamps else text)
    return "\n".join(lines).strip()


def json_transcript_to_markdown(value: Any, include_timestamps: bool) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("segments", "transcript", "results", "items", "captions"):
            if key in value:
                return json_transcript_to_markdown(value[key], include_timestamps)
        text = value.get("text") or value.get("body") or value.get("content")
        return str(text or "").strip()
    if not isinstance(value, list):
        return ""
    lines: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            start = None
            speaker = None
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("body") or item.get("content") or "").strip()
            start = item.get("start")
            if start is None:
                start = item.get("startTime") or item.get("start_time")
            speaker = item.get("speaker") or item.get("speakerName") or item.get("speaker_name")
        else:
            continue
        if not text:
            continue
        if speaker:
            text = f"{speaker}: {text}"
        if include_timestamps and start is not None:
            try:
                marker = str(dt.timedelta(seconds=int(float(start))))
            except (TypeError, ValueError):
                marker = caption_timestamp(str(start))
            text = f"[{marker}] {text}"
        lines.append(text)
    return "\n".join(lines).strip()


def convert_published_transcript(
    payload: bytes,
    content_type: str,
    source_url: str,
    include_timestamps: bool,
) -> str:
    text = payload.decode("utf-8-sig", errors="replace").strip()
    suffix = Path(urlparse(source_url).path).suffix.lower()
    content_type = (content_type or "").lower()
    if suffix in {".vtt", ".srt"} or "vtt" in content_type or "subrip" in content_type:
        return caption_blocks_to_markdown(text, include_timestamps)
    if suffix == ".json" or "json" in content_type:
        return json_transcript_to_markdown(json.loads(text), include_timestamps)
    if suffix in {".html", ".htm"} or "html" in content_type:
        parser = TextHTMLParser()
        parser.feed(text)
        return parser.text()
    return text


def fetch_published_transcript(
    transcript: dict[str, Any], include_timestamps: bool
) -> tuple[str, str, str]:
    url = str(transcript["url"])
    payload, content_type, final_url = http_bytes(url, max_bytes=50 * 1024 * 1024)
    declared_type = str(transcript.get("type") or "")
    converted = convert_published_transcript(
        payload, declared_type or content_type, final_url, include_timestamps
    )
    if not converted:
        raise RuntimeError("The published transcript was empty or had no recognized segments.")
    return converted, final_url, declared_type or content_type


def resolve_openai_api_key(cli_key: str | None, interactive: bool = False) -> str | None:
    for key in (
        cli_key,
        os.getenv("OPENAI_API_KEY"),
        os.getenv("OPENAI_KEY"),
        os.getenv("OPENAI_API_TOKEN"),
    ):
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    if interactive and sys.stdin.isatty():
        key = getpass("OpenAI API key: ").strip()
        if key:
            os.environ["OPENAI_API_KEY"] = key
            return key
    return None


def ffmpeg_executable() -> str:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    imageio_ffmpeg = ensure_module("imageio_ffmpeg")
    return str(imageio_ffmpeg.get_ffmpeg_exe())


def split_media_to_audio_chunks(
    media_path: Path, work_dir: Path, chunk_seconds: int
) -> list[Path]:
    # Granite Speech expects mono 16 kHz audio. PCM WAV also stays below
    # OpenAI's upload limit at the default five-minute chunk size.
    chunk_pattern = str(work_dir / "chunk_%04d.wav")
    subprocess.run(
        [
            ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(media_path), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", "-f", "segment", "-segment_time", str(chunk_seconds),
            "-reset_timestamps", "1", chunk_pattern,
        ],
        check=True,
    )
    chunks = sorted(work_dir.glob("chunk_*.wav"))
    if not chunks:
        raise RuntimeError(f"Could not extract audio chunks from {media_path}")
    return chunks


def transcribe_chunk_openai(
    audio_path: Path, model: str, api_key: str | None, ask_for_key: bool
) -> str:
    key = resolve_openai_api_key(api_key, interactive=ask_for_key)
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. It is required only when no published transcript exists."
        )
    openai = ensure_module("openai")
    client = openai.OpenAI(api_key=key)
    with audio_path.open("rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model, file=audio_file, response_format="text"
        )
    return str(result).strip()


def ollama_executable() -> str:
    executable = shutil.which("ollama")
    if executable:
        return executable
    mise_install = Path.home() / ".local/share/mise/installs/ollama/latest/bin/ollama"
    if mise_install.is_file():
        return str(mise_install)
    raise RuntimeError("Ollama is not installed or is not available on PATH.")


def ollama_installed_models(host: str) -> list[str]:
    try:
        tags = http_json(host.rstrip("/") + "/api/tags", timeout=10)
    except Exception:
        return []
    return [
        str(item.get("name") or item.get("model"))
        for item in tags.get("models", [])
        if item.get("name") or item.get("model")
    ]


def ollama_model_installed(model: str, host: str) -> bool:
    installed = ollama_installed_models(host)
    wanted = model if ":" in model else f"{model}:latest"
    return any(name == model or name == wanted for name in installed)


def resolve_transcriber(args: argparse.Namespace) -> str:
    if args.transcriber in {"auto", "ollama"} and ollama_model_installed(
        args.ollama_transcribe_model, args.ollama_host
    ):
        return "ollama"
    if args.transcriber == "ollama":
        raise RuntimeError(
            f"Ollama model {args.ollama_transcribe_model!r} is not installed or Ollama "
            f"is not reachable at {args.ollama_host}. Install it with: ollama pull "
            f"{args.ollama_transcribe_model}. No audio was downloaded."
        )
    if args.transcriber in {"auto", "openai"} and resolve_openai_api_key(
        args.openai_api_key, interactive=args.ask_openai_key
    ):
        return "openai"
    raise RuntimeError(
        "No audio transcription engine is ready. Start Ollama and install "
        f"{args.ollama_transcribe_model!r}, or set OPENAI_API_KEY. "
        "No audio was downloaded."
    )


ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def transcribe_chunk_ollama(audio_path: Path, model: str, host: str) -> str:
    prompt = (
        "Transcribe all speech in this audio verbatim. Use proper punctuation and "
        "capitalization. Do not summarize, add commentary, or omit content."
    )
    environment = os.environ.copy()
    environment["OLLAMA_HOST"] = host
    result = subprocess.run(
        [
            ollama_executable(), "run", model, "--nowordwrap",
            str(audio_path), prompt,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=1800,
        env=environment,
    )
    transcript = ANSI_ESCAPE.sub("", result.stdout).strip()
    transcript = re.sub(
        r"<?\|?(?:user|assistant|system|super|end)\|?>?",
        " ",
        transcript,
        flags=re.IGNORECASE,
    )
    # Some Granite/Ollama builds expose token separators as literal pipes.
    transcript = transcript.replace("|", " ")
    return re.sub(r"\s+", " ", transcript).strip()


def transcription_chunk_seconds(provider: str, requested: int | None) -> int:
    if requested is not None:
        if requested < 1:
            raise ValueError("--chunk-seconds must be at least 1")
        return requested
    # IBM's Granite Speech reference implementation uses 30-second windows.
    # OpenAI accepts much larger uploads, which avoids unnecessary API calls.
    return 30 if provider == "ollama" else 600


def transcribe_media(
    media_path: Path,
    provider: str,
    openai_model: str,
    ollama_model: str,
    ollama_host: str,
    api_key: str | None,
    ask_for_key: bool,
    chunk_seconds: int,
) -> str:
    with tempfile.TemporaryDirectory(prefix="podcast-chunks-") as temp_dir:
        chunks = split_media_to_audio_chunks(media_path, Path(temp_dir), chunk_seconds)
        parts: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            print(
                f"Transcribing chunk {index}/{len(chunks)} with {provider}...",
                file=sys.stderr,
                flush=True,
            )
            if provider == "ollama":
                text = transcribe_chunk_ollama(chunk, ollama_model, ollama_host)
            else:
                text = transcribe_chunk_openai(
                    chunk, openai_model, api_key, ask_for_key
                )
            if text:
                parts.append(f"<!-- chunk {index}/{len(chunks)} -->\n\n{text}")
        return "\n\n".join(parts).strip()


def split_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines():
        line_size = len(line) + 1
        if current and size + line_size > max_chars:
            chunks.append("\n".join(current))
            current, size = [], 0
        current.append(line)
        size += line_size
    if current:
        chunks.append("\n".join(current))
    return chunks


def openai_summary_text(client: Any, model: str, text: str, instruction: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ],
    )
    return str(response.choices[0].message.content).strip()


def summarize_openai(
    text: str, model: str, api_key: str | None, ask_for_key: bool
) -> str:
    key = resolve_openai_api_key(api_key, interactive=ask_for_key)
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set, so OpenAI summarization cannot run.")
    openai = ensure_module("openai")
    client = openai.OpenAI(api_key=key)
    chunks = split_text(text, 60_000)
    partials = [
        openai_summary_text(
            client,
            model,
            chunk,
            "Summarize this podcast transcript chunk. Preserve facts, arguments, and action items.",
        )
        for chunk in chunks
    ]
    if len(partials) == 1:
        return partials[0]
    return openai_summary_text(
        client,
        model,
        "\n\n".join(f"Chunk {index + 1}:\n{value}" for index, value in enumerate(partials)),
        "Combine these chunk summaries into overview, key points, action items, and notable quotes.",
    )


def summarize_ollama(text: str, model: str, host: str) -> tuple[str, str]:
    if model == "auto":
        tags = http_json(host.rstrip("/") + "/api/tags")
        models = [item.get("name") for item in tags.get("models", []) if item.get("name")]
        if not models:
            raise RuntimeError("Ollama is running but has no installed model.")
        model = str(models[0])
    response = http_json(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(
            {
                "model": model,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Summarize this podcast transcript with overview, key points, "
                            f"action items, and notable quotes.\n\n{text}"
                        ),
                    }
                ],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        timeout=300,
    )
    return str((response.get("message") or {}).get("content") or "").strip(), model


def sanitize_filename(value: str, fallback: str = "podcast episode") -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1F]', " ", str(value)).strip()
    safe = re.sub(r"\s+", " ", safe)
    return (safe[:140] or fallback).rstrip(". ")


def output_basename(metadata: dict[str, Any]) -> str:
    identity = metadata.get("episode_id") or metadata.get("apple_episode_id") or ""
    title = metadata.get("title") or "podcast episode"
    return sanitize_filename(f"{identity} {title}".strip())


def write_outputs(
    output_dir: Path,
    basename: str,
    transcript: str,
    metadata: dict[str, Any],
    summary: str | None = None,
) -> tuple[Path, Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{basename}.transcript.md"
    metadata_path = output_dir / f"{basename}.metadata.json"
    summary_path = output_dir / f"{basename}.summary.md" if summary else None
    transcript_path.write_text(transcript.rstrip() + "\n", encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if summary_path and summary:
        summary_path.write_text(summary.rstrip() + "\n", encoding="utf-8")
    return transcript_path, metadata_path, summary_path


def default_output_dir() -> Path:
    return Path.home() / "Documents" / "Podcast Transcripts"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve a public podcast episode and save its transcript as Markdown."
    )
    parser.add_argument("input", nargs="?", help="Spotify/Apple episode, RSS, transcript/audio URL, or local file")
    parser.add_argument("--file", help="Explicit local media or transcript file")
    parser.add_argument("--episode", help="Exact episode title for an RSS feed or resolver override")
    parser.add_argument("--rss-url", help="Publisher's public RSS feed override")
    parser.add_argument("--audio-url", help="Explicit public episode audio URL override")
    parser.add_argument("--resolve-only", action="store_true", help="Print resolution metadata without downloading or transcribing")
    parser.add_argument("--published-only", action="store_true", help="Require a publisher-supplied transcript; never transcribe audio")
    parser.add_argument("--force-audio", action="store_true", help="Ignore published transcripts and transcribe public audio")
    parser.add_argument("--no-timestamps", action="store_true", help="Remove VTT/SRT/JSON timestamps from converted transcripts")
    parser.add_argument("--country", default=os.getenv("PODCAST_COUNTRY", "US").upper(), help="Two-letter Apple catalog country (default: US)")
    parser.add_argument("--min-match-score", type=float, default=0.86, help="Minimum Spotify-to-public-catalog confidence (default: 0.86)")
    parser.add_argument("--max-download-mb", type=int, default=2048, help="Maximum public audio download size (default: 2048)")
    parser.add_argument(
        "--chunk-seconds", type=int, default=None,
        help="Seconds per chunk (default: 30 for Ollama, 600 for OpenAI)",
    )
    parser.add_argument(
        "--transcriber", choices=["auto", "ollama", "openai"], default="auto",
        help="Audio transcription engine (default: auto, preferring local Ollama)",
    )
    parser.add_argument("--openai-transcribe-model", default="whisper-1")
    parser.add_argument("--openai-api-key", default=None, help="Prefer OPENAI_API_KEY or .env to avoid shell history")
    parser.add_argument("--ask-openai-key", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--summarizer", choices=["openai", "ollama"], default="openai")
    parser.add_argument("--openai-summary-model", default="gpt-4o-mini")
    parser.add_argument("--ollama-model", default="auto")
    parser.add_argument(
        "--ollama-transcribe-model", default="gabegoodhart/granite4.1-speech:2b"
    )
    parser.add_argument("--ollama-host", default=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    parser.add_argument("--output-dir", default=str(default_output_dir()))
    return parser.parse_args(argv)


def local_input(path: Path, args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    suffix = path.suffix.lower()
    metadata: dict[str, Any] = {
        "source_platform": "local",
        "source_url": str(path.resolve()),
        "title": path.stem,
    }
    if suffix in MEDIA_SUFFIXES:
        provider = resolve_transcriber(args)
        chunk_seconds = transcription_chunk_seconds(provider, args.chunk_seconds)
        transcript = transcribe_media(
            path,
            provider,
            args.openai_transcribe_model,
            args.ollama_transcribe_model,
            args.ollama_host,
            args.openai_api_key,
            args.ask_openai_key,
            chunk_seconds,
        )
        metadata.update(
            {
                "transcript_source": f"{provider}_audio_transcription",
                "transcriber": provider,
                "transcribe_model": (
                    args.ollama_transcribe_model
                    if provider == "ollama"
                    else args.openai_transcribe_model
                ),
                "chunk_seconds": chunk_seconds,
            }
        )
        return transcript, metadata
    payload = path.read_bytes()
    transcript = convert_published_transcript(
        payload, "", path.resolve().as_uri(), not args.no_timestamps
    )
    metadata["transcript_source"] = "local_transcript"
    return transcript, metadata


def run_summary(transcript: str, args: argparse.Namespace, metadata: dict[str, Any]) -> str:
    if args.summarizer == "ollama":
        summary, model = summarize_ollama(transcript, args.ollama_model, args.ollama_host)
        metadata["summary_model"] = f"ollama:{model}"
        return summary
    summary = summarize_openai(
        transcript, args.openai_summary_model, args.openai_api_key, args.ask_openai_key
    )
    metadata["summary_model"] = f"openai:{args.openai_summary_model}"
    return summary


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(".env"))
    args = parse_args(argv)
    raw_input = args.file or args.input
    if not raw_input:
        raw_input = input("Paste a podcast episode URL, RSS feed, or local file: ").strip()
    source_path = Path(raw_input).expanduser()

    if source_path.exists():
        transcript, metadata = local_input(source_path, args)
    else:
        resolution = resolve_episode(raw_input, args)
        resolution["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        if args.resolve_only:
            print(json.dumps(resolution, indent=2, ensure_ascii=False))
            return 0
        transcript = ""
        metadata = resolution
        published_error = None
        transcripts = resolution.get("transcripts") or []
        if transcripts and not args.force_audio:
            try:
                print("Fetching publisher-supplied transcript...", file=sys.stderr)
                transcript, final_url, transcript_type = fetch_published_transcript(
                    transcripts[0], not args.no_timestamps
                )
                metadata.update(
                    {
                        "transcript_source": "publisher_transcript",
                        "transcript_url": final_url,
                        "transcript_type": transcript_type,
                    }
                )
            except Exception as exc:
                published_error = f"{type(exc).__name__}: {exc}"
                if args.published_only:
                    raise RuntimeError(f"Published transcript failed: {published_error}") from exc
        if not transcript:
            if args.published_only:
                raise ResolutionError("This episode has no publisher-supplied transcript.")
            audio_url = str(resolution.get("audio_url") or "")
            if not audio_url:
                raise ResolutionError(
                    "No public transcript or RSS audio enclosure was found. Spotify-hosted "
                    "audio is not downloaded. Supply --rss-url, --audio-url, or a local file."
                )
            provider = resolve_transcriber(args)
            chunk_seconds = transcription_chunk_seconds(provider, args.chunk_seconds)
            print("Downloading public RSS audio...", file=sys.stderr)
            with tempfile.TemporaryDirectory(prefix="podcast-transcript-") as temp_dir:
                audio_path = Path(temp_dir) / "episode.audio"
                download_file(audio_url, audio_path, args.max_download_mb * 1024 * 1024)
                transcript = transcribe_media(
                    audio_path,
                    provider,
                    args.openai_transcribe_model,
                    args.ollama_transcribe_model,
                    args.ollama_host,
                    args.openai_api_key,
                    args.ask_openai_key,
                    chunk_seconds,
                )
            metadata.update(
                {
                    "transcript_source": f"public_rss_audio_{provider}_transcription",
                    "transcriber": provider,
                    "transcribe_model": (
                        args.ollama_transcribe_model
                        if provider == "ollama"
                        else args.openai_transcribe_model
                    ),
                    "chunk_seconds": chunk_seconds,
                }
            )
            if published_error:
                metadata["published_transcript_warning"] = published_error

    metadata.setdefault("created_at", dt.datetime.now(dt.timezone.utc).isoformat())
    metadata["character_count"] = len(transcript)
    output_dir = Path(args.output_dir).expanduser().resolve()
    basename = output_basename(metadata)
    transcript_path, metadata_path, _ = write_outputs(
        output_dir, basename, transcript, metadata
    )
    print(f"Transcript: {transcript_path.resolve()}")
    print(f"Metadata:   {metadata_path.resolve()}")

    if args.summary:
        summary = run_summary(transcript, args, metadata)
        _, _, summary_path = write_outputs(
            output_dir, basename, transcript, metadata, summary
        )
        if summary_path:
            print(f"Summary:    {summary_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ResolutionError, RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
