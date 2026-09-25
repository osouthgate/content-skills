#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("podcast_transcribe.py")
SPEC = importlib.util.spec_from_file_location("podcast_transcribe", SCRIPT)
assert SPEC and SPEC.loader
podcast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(podcast)


RSS_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Example Show</title>
    <item>
      <title>A Different Episode</title>
      <guid>older-guid</guid>
      <enclosure url="https://media.example/older.mp3" type="audio/mpeg" />
    </item>
    <item>
      <title>Why APIs Matter</title>
      <guid>target-guid</guid>
      <pubDate>Sun, 07 Sep 2026 08:00:00 GMT</pubDate>
      <podcast:transcript url="transcripts/apis.vtt" type="text/vtt" language="en" />
      <enclosure url="audio/apis.mp3" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


class IdentifierTests(unittest.TestCase):
    def test_spotify_url_and_uri(self) -> None:
        expected = "7makk4oTQel546B0PZlDM5"
        self.assertEqual(podcast.spotify_episode_id(f"spotify:episode:{expected}"), expected)
        self.assertEqual(
            podcast.spotify_episode_id(
                f"https://open.spotify.com/intl-gb/episode/{expected}?si=abc"
            ),
            expected,
        )

    def test_apple_episode_id(self) -> None:
        self.assertEqual(
            podcast.apple_episode_id(
                "https://podcasts.apple.com/gb/podcast/example/id12345?i=67890"
            ),
            "67890",
        )

    def test_title_normalization(self) -> None:
        self.assertEqual(
            podcast.normalized_title("Episode #12 — Why APIs Matter!"),
            podcast.normalized_title("Ep 12: Why APIs Matter"),
        )
        self.assertEqual(
            podcast.normalized_title("100: NSO"),
            podcast.normalized_title("NSO"),
        )


class ResolverTests(unittest.TestCase):
    def test_parse_feed_finds_public_sources(self) -> None:
        show, episodes = podcast.parse_feed(RSS_FIXTURE, "https://feed.example/rss.xml")
        self.assertEqual(show, "Example Show")
        self.assertEqual(len(episodes), 2)
        target = episodes[1]
        self.assertEqual(target["audio_url"], "https://feed.example/audio/apis.mp3")
        self.assertEqual(
            target["transcripts"][0]["url"],
            "https://feed.example/transcripts/apis.vtt",
        )

    def test_choose_feed_episode_uses_title(self) -> None:
        _, episodes = podcast.parse_feed(RSS_FIXTURE, "https://feed.example/rss.xml")
        episode, score = podcast.choose_feed_episode(
            episodes, {"title": "Why APIs Matter"}, None
        )
        self.assertEqual(episode["guid"], "target-guid")
        self.assertEqual(score, 1.0)

    def test_choose_apple_candidate_requires_confidence(self) -> None:
        good = {
            "trackName": "Why APIs Matter",
            "collectionName": "Example Show",
            "episodeUrl": "https://media.example/apis.mp3",
            "trackTimeMillis": 3_600_000,
            "releaseDate": "2026-09-07T08:00:00Z",
        }
        bad = {
            "trackName": "A Totally Different Subject",
            "collectionName": "Other Show",
            "episodeUrl": "https://media.example/other.mp3",
        }
        expected = {
            "title": "Why APIs Matter",
            "podcast": "Example Show",
            "duration_ms": 3_600_000,
            "release_date": "2026-09-07",
        }
        with mock.patch.object(podcast, "apple_search_candidates", return_value=[bad, good]):
            selected, score = podcast.choose_apple_candidate(expected, "US", 0.86)
        self.assertEqual(selected, good)
        self.assertGreater(score, 0.99)

    def test_choose_apple_candidate_rejects_weak_match(self) -> None:
        candidate = {
            "trackName": "A Totally Different Subject",
            "collectionName": "Other Show",
            "episodeUrl": "https://media.example/other.mp3",
        }
        with mock.patch.object(
            podcast, "apple_search_candidates", return_value=[candidate]
        ):
            with self.assertRaises(podcast.ResolutionError):
                podcast.choose_apple_candidate(
                    {"title": "Why APIs Matter", "podcast": "Example Show"},
                    "US",
                    0.86,
                )

    def test_missing_openai_key_fails_before_audio_download(self) -> None:
        resolution = {
            "title": "Audio-only episode",
            "audio_url": "https://media.example/episode.mp3",
            "transcripts": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            podcast, "resolve_episode", return_value=resolution
        ), mock.patch.object(
            podcast, "ollama_model_installed", return_value=False
        ), mock.patch.object(
            podcast, "resolve_openai_api_key", return_value=None
        ), mock.patch.object(
            podcast, "download_file"
        ) as download:
            with self.assertRaisesRegex(RuntimeError, "No audio was downloaded"):
                podcast.main(
                    [
                        "https://open.spotify.com/episode/1vbROFe80yIFRPLTI2Krg4",
                        "--output-dir",
                        temp_dir,
                    ]
                )
        download.assert_not_called()


class TranscriberTests(unittest.TestCase):
    def test_auto_prefers_installed_ollama_model(self) -> None:
        args = podcast.parse_args(["episode.mp3"])
        with mock.patch.object(
            podcast, "ollama_model_installed", return_value=True
        ), mock.patch.object(podcast, "resolve_openai_api_key") as openai_key:
            self.assertEqual(podcast.resolve_transcriber(args), "ollama")
        openai_key.assert_not_called()

    def test_auto_falls_back_to_openai(self) -> None:
        args = podcast.parse_args(["episode.mp3"])
        with mock.patch.object(
            podcast, "ollama_model_installed", return_value=False
        ), mock.patch.object(
            podcast, "resolve_openai_api_key", return_value="secret"
        ):
            self.assertEqual(podcast.resolve_transcriber(args), "openai")

    def test_explicit_missing_ollama_model_is_actionable(self) -> None:
        args = podcast.parse_args(["episode.mp3", "--transcriber", "ollama"])
        with mock.patch.object(
            podcast, "ollama_model_installed", return_value=False
        ):
            with self.assertRaisesRegex(RuntimeError, "ollama pull"):
                podcast.resolve_transcriber(args)

    def test_ollama_chunk_uses_audio_file_and_cleans_terminal_codes(self) -> None:
        completed = mock.Mock(
            stdout="\x1b[?25l|user|> Hello\nworld. <|super|>\x1b[?25h\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "sample.wav"
            audio.touch()
            with mock.patch.object(
                podcast, "ollama_executable", return_value="/usr/bin/ollama"
            ), mock.patch.object(
                podcast.subprocess, "run", return_value=completed
            ) as run:
                result = podcast.transcribe_chunk_ollama(
                    audio, "speech-model:2b", "http://localhost:11434"
                )
        self.assertEqual(result, "Hello world.")
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["/usr/bin/ollama", "run", "speech-model:2b"])
        self.assertIn("--nowordwrap", command)
        self.assertIn(str(audio), command)

    def test_provider_specific_default_chunk_sizes(self) -> None:
        self.assertEqual(podcast.transcription_chunk_seconds("ollama", None), 30)
        self.assertEqual(podcast.transcription_chunk_seconds("openai", None), 600)
        self.assertEqual(podcast.transcription_chunk_seconds("ollama", 45), 45)


class TranscriptConversionTests(unittest.TestCase):
    def test_vtt_to_timestamped_markdown(self) -> None:
        raw = b"""WEBVTT

00:00:01.000 --> 00:00:03.000
<v Alice>Hello &amp; welcome.</v>

00:01:02.500 --> 00:01:04.000
Second line.
"""
        converted = podcast.convert_published_transcript(
            raw, "text/vtt", "https://example/transcript.vtt", True
        )
        self.assertEqual(
            converted,
            "[0:00:01] Alice: Hello & welcome.\n[0:01:02] Second line.",
        )

    def test_json_segments_to_markdown(self) -> None:
        raw = json.dumps(
            {"segments": [{"start": 5, "speaker": "Sam", "text": "Hello"}]}
        ).encode()
        converted = podcast.convert_published_transcript(
            raw, "application/json", "https://example/transcript.json", True
        )
        self.assertEqual(converted, "[0:00:05] Sam: Hello")

    def test_local_vtt_writes_matching_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "episode.vtt"
            output = root / "out"
            source.write_text(
                "WEBVTT\n\n00:00:02.000 --> 00:00:04.000\nHello\n",
                encoding="utf-8",
            )
            result = podcast.main([str(source), "--output-dir", str(output)])
            self.assertEqual(result, 0)
            transcripts = list(output.glob("*.transcript.md"))
            metadata = list(output.glob("*.metadata.json"))
            self.assertEqual(len(transcripts), 1)
            self.assertEqual(len(metadata), 1)
            self.assertIn("[0:00:02] Hello", transcripts[0].read_text())


if __name__ == "__main__":
    unittest.main()
