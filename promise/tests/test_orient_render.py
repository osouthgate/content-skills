"""Tests for orient.py, framework_section.py and render_outcome.py behaviours that
have a written rule behind them: refusals exit 2 with one line and never a
traceback; a config value that is wrong on disk is a warning, not a crash; the
doc scan ignores fenced illustrations; the mode hint reads a digit run as a date
before it reads it as a sha; the docs folder is created only when asked.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent / "skills" / "promise"
SCRIPTS_DIR = SKILL_DIR / "scripts"
ORIENT = SCRIPTS_DIR / "orient.py"
FRAMEWORK_SECTION = SCRIPTS_DIR / "framework_section.py"
RENDER = SCRIPTS_DIR / "render_outcome.py"
BUNDLED_FRAMEWORK = SKILL_DIR / "outcome-framework.md"

NOT_UTF8 = b"\xff\xfe\x00 not utf-8 \x80\x81"


def run(script: Path, *args: str, env: Optional[Dict[str, str]] = None, **kwargs: Any) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=full_env, **kwargs,
    )


def orientation(cwd: str, *args: str) -> Dict[str, Any]:
    result = run(ORIENT, "--cwd", cwd, *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def write_config(cwd: str, config: dict) -> None:
    config_dir = Path(cwd) / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def outcome_doc(title: str, status: str = "draft", prefix: str = "") -> str:
    return (
        f"{prefix}# {title}\n\nStatus: {status}\nOwner: Priya        Last decision: 2026-01-01\n\n"
        "## 0. TLDR\n**Outcome:** placeholder.\n**Rules:**\n- placeholder rule.  → AT-1\n"
        "**How we'll know:** placeholder.\n**Scenarios:** 1 acceptance rows (§6), 0 worked examples (§3).\n"
    )


class TempProject(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name
        self.root = Path(self.cwd)


# ---------------------------------------------------------------------------
# orient.py: invocation refusals and the mode key
# ---------------------------------------------------------------------------


class OrientInvocation(TempProject):
    def test_mode_is_null_without_the_flag(self) -> None:
        self.assertIsNone(orientation(self.cwd)["mode"])

    def test_mode_is_echoed_or_infer_with_the_flag(self) -> None:
        self.assertEqual(orientation(self.cwd, "--mode", "arm")["mode"], "arm")
        self.assertEqual(orientation(self.cwd, "--mode", "frobnicate")["mode"], "infer")

    def test_missing_cwd_is_refused(self) -> None:
        result = run(ORIENT, "--cwd", os.path.join(self.cwd, "nope"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such directory", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cwd_that_is_a_file_is_refused(self) -> None:
        a_file = self.root / "file.txt"
        a_file.write_text("x", encoding="utf-8")
        result = run(ORIENT, "--cwd", str(a_file))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such directory", result.stderr)

    def test_non_utf8_input_file_is_refused_without_traceback(self) -> None:
        msg = self.root / "msg.txt"
        msg.write_bytes(NOT_UTF8)
        result = run(ORIENT, "--cwd", self.cwd, "--input-file", str(msg))
        self.assertEqual(result.returncode, 2)
        self.assertIn("not UTF-8", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_help_and_source_say_section_sign_not_ss(self) -> None:
        result = run(ORIENT, "-h")
        self.assertEqual(result.returncode, 0)
        self.assertIn("§4", result.stdout)
        self.assertNotIn("SS4", result.stdout)
        source = ORIENT.read_text(encoding="utf-8")
        for script in (ORIENT, FRAMEWORK_SECTION, RENDER):
            self.assertNotRegex(script.read_text(encoding="utf-8"), r"SS\d", f"{script.name} still spells SS<digit>")
        self.assertIn("§5", source)

    def test_stdout_degrades_instead_of_crashing_on_an_ascii_console(self) -> None:
        docs = self.root / "docs" / "designs"
        docs.mkdir(parents=True)
        (docs / "cafe.md").write_text(outcome_doc("Café"), encoding="utf-8")
        result = run(ORIENT, "--cwd", self.cwd, env={"PYTHONIOENCODING": "ascii"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(json.loads(result.stdout)["existingDocs"][0]["title"], "Caf?")


# ---------------------------------------------------------------------------
# orient.py: config warnings
# ---------------------------------------------------------------------------


class OrientConfigWarnings(TempProject):
    def test_schema_key_is_accepted_but_deprecated(self) -> None:
        write_config(self.cwd, {"$schema": "promise.config/v1"})
        data = orientation(self.cwd)
        self.assertTrue(data["config"]["loaded"])
        self.assertFalse(any("unknown config key" in w for w in data["warnings"]))
        self.assertTrue(any('"$schema" is deprecated' in w for w in data["warnings"]), data["warnings"])

    def test_version_1_is_silent_and_other_versions_warn(self) -> None:
        write_config(self.cwd, {"version": 1})
        data = orientation(self.cwd)
        self.assertFalse(any("version" in w for w in data["warnings"]), data["warnings"])
        write_config(self.cwd, {"version": 2})
        data = orientation(self.cwd)
        self.assertTrue(any("unsupported config version: 2" in w for w in data["warnings"]), data["warnings"])

    def test_config_docs_home_that_does_not_exist_warns_and_is_still_returned(self) -> None:
        write_config(self.cwd, {"docsHome": "docs/not-yet"})
        data = orientation(self.cwd)
        self.assertEqual(data["docsHome"], "docs/not-yet")
        self.assertEqual(data["docsHomeSource"], "config")
        self.assertTrue(any("docsHome does not exist: docs/not-yet" in w for w in data["warnings"]), data["warnings"])

    def test_existing_config_docs_home_does_not_warn(self) -> None:
        (self.root / "docs" / "rfcs").mkdir(parents=True)
        write_config(self.cwd, {"docsHome": "docs/rfcs"})
        data = orientation(self.cwd)
        self.assertFalse(any("docsHome does not exist" in w for w in data["warnings"]))

    def test_map_recipe_and_index_that_do_not_exist_warn_without_flipping_usable(self) -> None:
        write_config(self.cwd, {"map": {
            "recipe": "docs/recipe.md", "index": "docs/index.md", "find": "f", "row": "r",
            "lanes": {"data": "tests[]"},
        }})
        data = orientation(self.cwd)
        self.assertTrue(data["mapUsable"])
        self.assertTrue(any("map.recipe does not exist: docs/recipe.md" in w for w in data["warnings"]), data["warnings"])
        self.assertTrue(any("map.index does not exist: docs/index.md" in w for w in data["warnings"]), data["warnings"])

    def test_map_recipe_that_exists_does_not_warn(self) -> None:
        (self.root / "docs").mkdir()
        (self.root / "docs" / "recipe.md").write_text("# recipe\n", encoding="utf-8")
        write_config(self.cwd, {"map": {"recipe": "docs/recipe.md", "find": "f", "row": "r", "lanes": {"data": "t[]"}}})
        data = orientation(self.cwd)
        self.assertFalse(any("map.recipe" in w for w in data["warnings"]), data["warnings"])

    def test_map_recipe_that_escapes_the_project_warns(self) -> None:
        write_config(self.cwd, {"map": {"recipe": "../recipe.md", "find": "f", "row": "r", "lanes": {"data": "t[]"}}})
        data = orientation(self.cwd)
        self.assertTrue(any("path escapes the project: map.recipe" in w for w in data["warnings"]), data["warnings"])

    def test_windows_absolute_paths_escape_on_every_os(self) -> None:
        # A drive-letter path is absolute whatever OS reads the config:
        # os.path.isabs alone would pass it on POSIX and hand render_outcome.py
        # a "project-relative" C:/Users/x/docs.
        write_config(self.cwd, {
            "docsHome": "C:\\Users\\x\\docs",
            "frameworkPath": "D:/fw.md",
            "map": {"recipe": "C:\\r.md", "find": "f", "row": "r", "lanes": {"data": "t"}},
        })
        data = orientation(self.cwd)
        self.assertNotEqual(data["docsHomeSource"], "config")
        self.assertEqual(data["frameworkSource"], "bundled")
        for key in ("docsHome", "frameworkPath", "map.recipe"):
            self.assertTrue(any(f"path escapes the project: {key}" in w for w in data["warnings"]), (key, data["warnings"]))
        self.assertFalse(any(w.startswith("docsHome does not exist") for w in data["warnings"]), data["warnings"])

    def test_loaded_config_with_no_docs_home_and_nothing_detected_warns(self) -> None:
        write_config(self.cwd, {"version": 1})
        data = orientation(self.cwd)
        self.assertIsNone(data["docsHome"])
        self.assertEqual(data["docsHomeSource"], "none")
        self.assertTrue(any(w.startswith("docsHome is null") and "--docs-home" in w for w in data["warnings"]), data["warnings"])

    def test_no_config_at_all_does_not_carry_the_null_docs_home_warning(self) -> None:
        # Without a config there is nothing to pin it in; the "no config"
        # warning already covers the project.
        data = orientation(self.cwd)
        self.assertIsNone(data["docsHome"])
        self.assertFalse(any(w.startswith("docsHome is null") for w in data["warnings"]), data["warnings"])

    def test_backslash_docs_home_is_normalised_with_a_warning(self) -> None:
        (self.root / "docs" / "designs").mkdir(parents=True)
        write_config(self.cwd, {"docsHome": "docs\\designs"})
        data = orientation(self.cwd)
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertEqual(data["docsHomeSource"], "config")
        self.assertTrue(any("docsHome uses backslashes" in w for w in data["warnings"]), data["warnings"])
        self.assertFalse(any("docsHome does not exist" in w for w in data["warnings"]), data["warnings"])

    def test_backslash_framework_path_resolves_to_the_project_copy(self) -> None:
        (self.root / "docs" / "how-to").mkdir(parents=True)
        (self.root / "docs" / "how-to" / "fw.md").write_text("## The contract\nx\n", encoding="utf-8")
        write_config(self.cwd, {"frameworkPath": "docs\\how-to\\fw.md"})
        data = orientation(self.cwd)
        self.assertEqual(data["frameworkSource"], "project")
        self.assertTrue(any("frameworkPath uses backslashes" in w for w in data["warnings"]), data["warnings"])

    def test_backslash_map_recipe_warns_and_map_stays_verbatim(self) -> None:
        raw_map = {"recipe": "docs\\recipe.md", "find": "f", "row": "r", "lanes": {"data": "t[]"}}
        write_config(self.cwd, {"map": raw_map})
        data = orientation(self.cwd)
        self.assertEqual(data["map"], raw_map)
        self.assertTrue(any("map.recipe uses backslashes" in w for w in data["warnings"]), data["warnings"])

    def test_checks_and_issue_tracker_shapes_warn(self) -> None:
        write_config(self.cwd, {"map": {
            "recipe": "r.md", "find": "f", "row": "r", "lanes": {"data": "t[]"},
            "checks": 123, "issueTracker": "github",
        }})
        data = orientation(self.cwd)
        self.assertTrue(any("map.checks is not an array of strings" in w for w in data["warnings"]), data["warnings"])
        self.assertTrue(any("map.issueTracker is not an object" in w for w in data["warnings"]), data["warnings"])

    def test_well_formed_checks_and_issue_tracker_do_not_warn(self) -> None:
        write_config(self.cwd, {"map": {
            "recipe": "r.md", "find": "f", "row": "r", "lanes": {"data": "t[]"},
            "checks": ["a", "b"], "issueTracker": {"kind": "github", "repo": "o/r", "template": "t.md"},
        }})
        data = orientation(self.cwd)
        self.assertFalse(any("map.checks" in w or "map.issueTracker" in w for w in data["warnings"]), data["warnings"])


# ---------------------------------------------------------------------------
# orient.py: the existing-docs scan
# ---------------------------------------------------------------------------


class OrientDocScan(TempProject):
    def setUp(self) -> None:
        super().setUp()
        self.docs = self.root / "docs" / "designs"
        self.docs.mkdir(parents=True)

    def test_a_fenced_tldr_heading_is_not_an_outcome_doc(self) -> None:
        (self.docs / "notes.md").write_text(
            "# Notes\n\n```markdown\n## 0. TLDR\n- fake → UNTESTED\n```\n", encoding="utf-8"
        )
        self.assertEqual(orientation(self.cwd)["existingDocs"], [])

    def test_a_framework_copy_in_docs_home_is_not_an_outcome_doc(self) -> None:
        (self.docs / "outcome-framework.md").write_bytes(BUNDLED_FRAMEWORK.read_bytes())
        self.assertEqual(orientation(self.cwd)["existingDocs"], [])

    def test_a_real_doc_with_a_fenced_illustration_above_it_is_read_from_the_unfenced_text(self) -> None:
        prefix = "```\n# Not The Title\nStatus: agreed\n## 0. TLDR\n```\n"
        (self.docs / "real.md").write_text(outcome_doc("Real Title", "draft", prefix), encoding="utf-8")
        docs = orientation(self.cwd)["existingDocs"]
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["title"], "Real Title")
        self.assertEqual(docs[0]["status"], "draft")

    def test_a_doc_one_folder_down_is_listed_and_every_scan_agrees(self) -> None:
        # docsHome is read one level deep by orient, lint_outcome.py and
        # outcome_rows.py --search alike: a doc in docsHome/sub/ is listed
        # here, linted at every hand-back, and matched by intake's search.
        # Two levels down is outside every one of them.
        (self.root / "docs" / "designs" / "sub" / "deeper").mkdir(parents=True)
        (self.root / "docs" / "designs" / "top.md").write_text(outcome_doc("Top"), encoding="utf-8")
        (self.root / "docs" / "designs" / "sub" / "nested.md").write_text(outcome_doc("Nested"), encoding="utf-8")
        (self.root / "docs" / "designs" / "sub" / "deeper" / "buried.md").write_text(outcome_doc("Buried"), encoding="utf-8")
        docs = orientation(self.cwd)["existingDocs"]
        self.assertEqual([d["path"] for d in docs], ["docs/designs/sub/nested.md", "docs/designs/top.md"])
        self.assertEqual({d["title"] for d in docs}, {"Top", "Nested"})

        lint = run(SCRIPTS_DIR / "lint_outcome.py", str(self.root / "docs" / "designs"), "--json")
        linted = sorted(os.path.relpath(r["path"], self.cwd).replace(os.sep, "/") for r in json.loads(lint.stdout))
        self.assertEqual(linted, ["docs/designs/sub/nested.md", "docs/designs/top.md"])

        search = run(SCRIPTS_DIR / "outcome_rows.py", "--search", "placeholder rule", "--dir", str(self.root / "docs" / "designs"), "--json")
        self.assertEqual(search.returncode, 0, search.stderr)
        searched = sorted({os.path.relpath(r["doc"], self.cwd).replace(os.sep, "/") for r in json.loads(search.stdout)})
        self.assertEqual(searched, ["docs/designs/sub/nested.md", "docs/designs/top.md"])

    def test_a_non_utf8_doc_is_skipped_with_a_warning_and_the_rest_are_listed(self) -> None:
        (self.docs / "bad.md").write_bytes(NOT_UTF8)
        (self.docs / "good.md").write_text(outcome_doc("Good"), encoding="utf-8")
        data = orientation(self.cwd)
        self.assertEqual([d["title"] for d in data["existingDocs"]], ["Good"])
        self.assertTrue(any("skipped unreadable doc docs/designs/bad.md" in w for w in data["warnings"]), data["warnings"])


# ---------------------------------------------------------------------------
# orient.py: the mode hint and detection
# ---------------------------------------------------------------------------


class OrientHint(TempProject):
    def hint(self, text: str) -> Dict[str, Any]:
        return orientation(self.cwd, "--input", text)

    def test_a_compact_date_in_a_design_request_stays_new(self) -> None:
        data = self.hint("design mute for a channel, target date 20260914")
        self.assertEqual(data["suggestedMode"], "new")
        self.assertFalse(data["ambiguous"])

    def test_an_unprefixed_digit_only_id_stays_new(self) -> None:
        self.assertEqual(self.hint("design channel mute; see issue 1234567")["suggestedMode"], "new")

    def test_a_hex_sha_still_reconciles(self) -> None:
        data = self.hint("the widget is in 7c65fab")
        self.assertEqual(data["suggestedMode"], "reconcile")
        self.assertTrue(any("7c65fab" in s for s in data["signals"]))

    def test_a_digit_only_sha_beside_a_shipped_word_still_reconciles(self) -> None:
        self.assertEqual(self.hint("shipped in 1234567")["suggestedMode"], "reconcile")

    def test_a_plain_complaint_sentence_leans_intake(self) -> None:
        self.assertEqual(self.hint("customers complain that search returns nothing")["suggestedMode"], "intake")

    def test_bun_text_lockfile_is_detected(self) -> None:
        (self.root / "package.json").write_text(json.dumps({"scripts": {"test": "x"}}), encoding="utf-8")
        (self.root / "bun.lock").write_text("", encoding="utf-8")
        self.assertEqual(orientation(self.cwd)["commands"]["test"], "bun test")


# ---------------------------------------------------------------------------
# framework_section.py
# ---------------------------------------------------------------------------


class FrameworkSection(TempProject):
    def test_no_arguments_is_a_usage_error_with_a_message(self) -> None:
        result = run(FRAMEWORK_SECTION, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("usage", result.stderr)
        self.assertIn("--list", result.stderr)

    def test_list_still_exits_zero(self) -> None:
        result = run(FRAMEWORK_SECTION, "--cwd", self.cwd, "--list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], f"# {BUNDLED_FRAMEWORK}")

    def test_escaping_framework_path_falls_back_to_bundled_like_orient(self) -> None:
        outside = Path(self.cwd).parent / f"{Path(self.cwd).name}-outside.md"
        outside.write_text("## Only Here\nx\n", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        for value in (f"../{outside.name}", str(outside)):
            write_config(self.cwd, {"frameworkPath": value})
            result = run(FRAMEWORK_SECTION, "--cwd", self.cwd, "--list")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines()[0], f"# {BUNDLED_FRAMEWORK}", value)
            self.assertIn("path escapes the project: frameworkPath", result.stderr)
            self.assertNotIn("Only Here", result.stdout)

    def test_project_framework_path_is_used(self) -> None:
        (self.root / "docs").mkdir()
        (self.root / "docs" / "fw.md").write_text("## Only Here\nbody\n", encoding="utf-8")
        write_config(self.cwd, {"frameworkPath": "docs/fw.md"})
        result = run(FRAMEWORK_SECTION, "--cwd", self.cwd, "Only Here")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("## Only Here", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_non_utf8_framework_is_refused_without_traceback(self) -> None:
        bad = self.root / "fw.md"
        bad.write_bytes(NOT_UTF8)
        result = run(FRAMEWORK_SECTION, "--framework", str(bad), "--list")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not UTF-8", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_cwd_is_refused(self) -> None:
        result = run(FRAMEWORK_SECTION, "--cwd", os.path.join(self.cwd, "nope"), "--list")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such directory", result.stderr)


# ---------------------------------------------------------------------------
# render_outcome.py
# ---------------------------------------------------------------------------


class RenderDocsHome(TempProject):
    def render(self, *args: str) -> subprocess.CompletedProcess:
        return run(RENDER, "--cwd", self.cwd, "--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01", *args)

    def test_missing_folder_is_refused_and_names_the_flag(self) -> None:
        result = self.render("--docs-home", "docs/designs")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--create-docs-home", result.stderr)
        self.assertFalse((self.root / "docs").exists())

    def test_dry_run_needs_neither_the_folder_nor_the_flag(self) -> None:
        result = self.render("--docs-home", "docs/designs", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["written"])
        self.assertFalse((self.root / "docs").exists())

    def test_the_flag_creates_the_folder_and_writes(self) -> None:
        result = self.render("--docs-home", "docs/designs", "--create-docs-home", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["written"])
        self.assertTrue((self.root / "docs" / "designs" / "channel-muting.md").is_file())

    def test_dry_run_with_the_flag_creates_nothing(self) -> None:
        result = self.render("--docs-home", "docs/designs", "--create-docs-home", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Channel Muting", result.stdout)
        self.assertFalse((self.root / "docs").exists())

    def test_config_docs_home_that_does_not_exist_is_refused_without_the_flag(self) -> None:
        write_config(self.cwd, {"docsHome": "docs/rfcs"})
        result = self.render()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--create-docs-home", result.stderr)
        self.assertFalse((self.root / "docs").exists())

    def test_docs_home_that_is_a_file_is_refused_without_traceback(self) -> None:
        (self.root / "docs").write_text("not a folder", encoding="utf-8")
        for extra in (("--create-docs-home",), ("--dry-run",)):
            result = self.render("--docs-home", "docs", *extra)
            self.assertEqual(result.returncode, 2, extra)
            self.assertIn("not a directory", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


class RenderArguments(TempProject):
    def setUp(self) -> None:
        super().setUp()
        self.docs = self.root / "docs" / "designs"
        self.docs.mkdir(parents=True)

    def render(self, *args: str) -> subprocess.CompletedProcess:
        return run(RENDER, "--cwd", self.cwd, "--docs-home", "docs/designs", *args)

    def test_empty_slug_is_refused_and_no_hidden_file_is_written(self) -> None:
        result = self.render("--title", "日本語だけ", "--owner", "Ana", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("empty slug", result.stderr)
        self.assertFalse((self.docs / ".md").exists())
        self.assertEqual(sorted(p.name for p in self.docs.iterdir()), [])

    def test_slug_override_names_the_file(self) -> None:
        result = self.render("--title", "日本語だけ", "--owner", "Ana", "--slug", "japanese-only", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["slug"], "japanese-only")
        self.assertTrue((self.docs / "japanese-only.md").is_file())
        self.assertTrue((self.docs / "japanese-only.md").read_text(encoding="utf-8").startswith("# 日本語だけ\n"))

    def test_slug_override_must_be_slug_form(self) -> None:
        # a value starting with "-" never reaches the script (argparse reads it as a flag)
        for bad in ("Bad Slug", "", "trailing-", "has.dot", "Upper"):
            result = self.render("--title", "Fine", "--owner", "Ana", "--slug", bad)
            self.assertEqual(result.returncode, 2, bad)
            self.assertIn("slug form", result.stderr)

    def test_date_must_be_a_real_iso_date(self) -> None:
        for bad in ("2026-02-30", "20260914", "14/09/2026", "yesterday", "2026-9-4"):
            result = self.render("--title", "Fine", "--owner", "Ana", "--date", bad, "--dry-run")
            self.assertEqual(result.returncode, 2, bad)
            self.assertIn("not a calendar date", result.stderr)
        good = self.render("--title", "Fine", "--owner", "Ana", "--date", "2024-02-29", "--dry-run")
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn("Last decision: 2024-02-29", good.stdout)

    def test_newlines_in_title_or_owner_are_refused(self) -> None:
        for args in (("--title", "Two\nLines", "--owner", "Ana"), ("--title", "Fine", "--owner", "Ana\rSmith")):
            result = self.render(*args, "--dry-run")
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("one line", result.stderr)

    def test_blank_title_or_owner_is_refused(self) -> None:
        for args in (("--title", "   ", "--owner", "Ana"), ("--title", "Fine", "--owner", "")):
            result = self.render(*args, "--dry-run")
            self.assertEqual(result.returncode, 2, args)
            self.assertIn("blank", result.stderr)

    def test_dry_run_stdout_degrades_on_an_ascii_console(self) -> None:
        result = run(
            RENDER, "--cwd", self.cwd, "--docs-home", "docs/designs", "--title", "Fine", "--owner", "Ana", "--dry-run",
            env={"PYTHONIOENCODING": "ascii"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("# Fine", result.stdout)

    def test_help_documents_the_new_flags(self) -> None:
        result = run(RENDER, "-h")
        self.assertEqual(result.returncode, 0)
        for flag in ("--create-docs-home", "--slug", "--date"):
            self.assertIn(flag, result.stdout)


if __name__ == "__main__":
    unittest.main()
