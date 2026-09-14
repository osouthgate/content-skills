"""Hardening tests for the promise skill's adopt.py script.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Mirrors test_scripts.py's own conventions: the script is located relative
to this file and exercised as a real subprocess (argv, stdout, stderr,
exit code). Every scenario is built in a temporary directory. What is
locked here, one class each: the config it writes ("version": 1, all
three command keys once any is detected), a prose fallback that is not
rendered as code, a symlinked CLAUDE.md that keeps its link, file modes
that survive the write, a docsHome that would break the managed block,
whitespace around the end marker, and refusals — not tracebacks — for a
wrong-typed path or a CLAUDE.md that is not text.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
ADOPT = SCRIPTS_DIR / "adopt.py"

BEGIN_PREFIX = "<!-- promise:begin"
END_MARKER = "<!-- promise:end -->"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ADOPT), *args], capture_output=True, text=True)


def run_json(*args: str) -> Tuple[subprocess.CompletedProcess, Optional[dict]]:
    result = run(*args)
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


class ConfigShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.config_path = self.cwd / ".claude" / "promise.config.json"

    def _config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def test_fresh_config_carries_version_1_and_no_schema_key(self) -> None:
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = self._config()
        self.assertEqual(config["version"], 1)
        self.assertNotIn("$schema", config)
        # version is the first key, where a reader looks for it
        self.assertEqual(list(config.keys())[0], "version")

    def test_no_detected_commands_means_no_commands_object(self) -> None:
        # Omitting the object leaves detection on for a project that
        # later gains a package.json; writing three nulls would pin it off.
        run("--cwd", str(self.cwd))
        self.assertNotIn("commands", self._config())

    def test_detected_commands_are_written_with_all_three_keys(self) -> None:
        # A package.json with only a test script: the config must show
        # typeCheck and lint pinned to null, because once a commands
        # object exists detection is off for all three.
        (self.cwd / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"test": "vitest run"}}), encoding="utf-8"
        )
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self._config()["commands"]
        self.assertEqual(set(commands.keys()), {"typeCheck", "test", "lint"})
        self.assertEqual(commands["test"], "npm run test")
        self.assertIsNone(commands["typeCheck"])
        self.assertIsNone(commands["lint"])

    def test_docs_home_flag_is_recorded(self) -> None:
        run("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(self._config()["docsHome"], "docs/rfcs")

    def test_docs_home_flag_is_reported_in_json(self) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/rfcs")

    def test_no_docs_home_says_so_on_stderr(self) -> None:
        # An empty project: nothing detected, no flag. The config is still
        # written (exit 0) but pins no docsHome, and stderr says what that
        # costs and how to fix it — the JSON shows the null too.
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("docsHome", self._config())
        self.assertIsNone(data["docsHome"])
        self.assertIn("--docs-home", result.stderr)
        self.assertIn("every later `new` will ask", result.stderr)

    def test_a_detected_docs_home_does_not_warn(self) -> None:
        (self.cwd / "docs" / "designs").mkdir(parents=True)
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertNotIn("--docs-home", result.stderr)

    def test_backslash_docs_home_is_recorded_with_forward_slashes(self) -> None:
        # The config contract asks for forward slashes; a value written the
        # Windows way is recorded in that form so orient never warns about
        # a file this script wrote.
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs\\designs", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"docsHome": "docs/designs"', result.stderr)
        self.assertIn("lives in `docs/designs`", result.stderr)
        self.assertNotIn("\\", result.stderr.split("---", 1)[-1])
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertIn("backslashes", result.stderr)


class DocsHomeDriftTests(unittest.TestCase):
    """On an already-adopted project, a --docs-home that disagrees with the
    loaded config is refused before any write: CLAUDE.md and the config
    must never name different folders."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def test_disagreeing_docs_home_is_refused_and_claude_md_is_untouched(self) -> None:
        first = run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = (self.cwd / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("docs/designs", before)

        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("disagrees", result.stderr)
        self.assertIn("docs/designs", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(data["changed"])
        self.assertEqual((self.cwd / "CLAUDE.md").read_text(encoding="utf-8"), before)

    def test_agreeing_docs_home_is_a_no_op(self) -> None:
        run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(data["changed"])


class ProseFallbackRenderingTests(unittest.TestCase):
    """The backticks belong to the value: a real path is code, a prose
    fallback is prose. Checked on the dry-run diff, which carries the
    rendered block verbatim."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _rendered(self, *args: str) -> str:
        run("--cwd", str(self.cwd), *args)
        return (self.cwd / "CLAUDE.md").read_text(encoding="utf-8")

    def test_unknown_docs_home_is_prose_not_code(self) -> None:
        text = self._rendered()
        self.assertIn("lives in the project's docs home,", text)
        self.assertNotIn("`the project's docs home`", text)

    def test_bundled_framework_is_prose_not_code(self) -> None:
        text = self._rendered()
        self.assertIn("(the copy bundled with the promise skill)", text)
        self.assertNotIn("`the copy bundled with the promise skill`", text)

    def test_a_real_docs_home_is_code(self) -> None:
        text = self._rendered("--docs-home", "docs/rfcs")
        self.assertIn("lives in `docs/rfcs`,", text)
        self.assertNotIn("``docs/rfcs``", text)

    def test_config_path_is_code_exactly_once(self) -> None:
        text = self._rendered()
        self.assertIn("`.claude/promise.config.json`", text)
        self.assertNotIn("``.claude/promise.config.json``", text)

    def test_a_project_framework_copy_is_code(self) -> None:
        (self.cwd / "docs").mkdir()
        (self.cwd / "docs" / "outcome-framework.md").write_text("# framework\n", encoding="utf-8")
        claude_dir = self.cwd / ".claude"
        claude_dir.mkdir()
        (claude_dir / "promise.config.json").write_text(
            json.dumps({"version": 1, "frameworkPath": "docs/outcome-framework.md", "map": None}),
            encoding="utf-8",
        )
        text = self._rendered()
        self.assertIn("(`docs/outcome-framework.md`)", text)


@unittest.skipIf(os.name == "nt", "symlinks and POSIX modes")
class SymlinkAndModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def test_symlinked_claude_md_keeps_its_link_and_the_target_gets_the_section(self) -> None:
        agents = self.cwd / "AGENTS.md"
        agents.write_text("# Agents\n\nShared notes.\n", encoding="utf-8")
        link = self.cwd / "CLAUDE.md"
        os.symlink("AGENTS.md", str(link))

        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(data["claudeMdWritten"])
        self.assertTrue(os.path.islink(link), "the link must survive the write")
        self.assertEqual(os.readlink(link), "AGENTS.md")
        target_text = agents.read_text(encoding="utf-8")
        self.assertIn("Shared notes.", target_text)
        self.assertIn(BEGIN_PREFIX, target_text)
        self.assertIn(END_MARKER, target_text)

        second, data2 = run_json("--cwd", str(self.cwd))
        self.assertEqual(second.returncode, 0)
        self.assertFalse(data2["changed"], "a rerun through the link is still a no-op")

    def test_existing_claude_md_keeps_its_mode(self) -> None:
        claude_md = self.cwd / "CLAUDE.md"
        claude_md.write_text("# Notes\n", encoding="utf-8")
        os.chmod(claude_md, 0o664)
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(claude_md).st_mode), 0o664)

    def test_new_files_are_not_owner_only(self) -> None:
        # mkstemp creates 0600; the written files must end up with what
        # open(2) would have given them under the umask instead.
        old_umask = os.umask(0o022)
        self.addCleanup(os.umask, old_umask)
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in (self.cwd / "CLAUDE.md", self.cwd / ".claude" / "promise.config.json"):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644, path)


class DocsHomeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _assert_refused(self, value: str, fragment: str) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", value)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIsNotNone(data, "stdout is always JSON")
        self.assertFalse(data["changed"])
        self.assertEqual(list(self.cwd.iterdir()), [], "nothing is written on a refusal")

    def test_newline_in_docs_home_is_refused(self) -> None:
        self._assert_refused("docs/designs\n<!-- promise:end -->", "single line")

    def test_marker_text_in_docs_home_is_refused(self) -> None:
        self._assert_refused("docs <!-- promise:end -->", "marker")

    def test_absolute_docs_home_is_refused(self) -> None:
        self._assert_refused(str(self.cwd / "docs"), "relative")

    def test_windows_drive_letter_docs_home_is_refused_on_every_os(self) -> None:
        # orient's rule, shared: a drive letter is absolute whatever OS the
        # script runs on.
        self._assert_refused("C:\\Users\\x\\docs", "relative")
        self._assert_refused("D:docs", "relative")

    def test_escaping_docs_home_is_refused(self) -> None:
        self._assert_refused("../elsewhere", "escape")

    def test_idempotency_holds_because_a_marker_never_reaches_the_file(self) -> None:
        # The failure this guards: a docsHome carrying an end marker used
        # to render into CLAUDE.md and make the next run refuse on
        # duplicated markers. Now the first run refuses and the second
        # (with a sane value) adopts and reruns clean.
        run("--cwd", str(self.cwd), "--docs-home", "docs\n<!-- promise:end -->")
        first = run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertFalse(data["changed"])


class EndMarkerWhitespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.claude_md = self.cwd / "CLAUDE.md"

    def test_trailing_whitespace_after_the_end_marker_is_tolerated(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        self.assertTrue(original.rstrip("\n").endswith(END_MARKER))
        with_trailing = original.rstrip("\n") + "   \n\n## Trailer\n\nKeep this.\n"
        self.claude_md.write_text(with_trailing, encoding="utf-8")

        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("end at line none", result.stderr)
        after = self.claude_md.read_text(encoding="utf-8")
        self.assertIn("Keep this.", after)
        self.assertEqual(after.count(END_MARKER), 1)

    def test_indented_end_marker_is_tolerated(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        indented = original.replace(END_MARKER, "  " + END_MARKER)
        self.assertNotEqual(indented, original)
        self.claude_md.write_text(indented, encoding="utf-8")
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_restoring_a_hand_edited_block_says_so_on_stderr(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        self.claude_md.write_text(original.replace("Say what you want", "VANDALISED"), encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(data["claudeMdWritten"])
        self.assertIn("differed from the rendered form", result.stderr)

    def test_a_clean_rerun_does_not_claim_a_restore(self) -> None:
        run("--cwd", str(self.cwd))
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(data["changed"])
        self.assertNotIn("differed from the rendered form", result.stderr)


class WrongTypedPathTests(unittest.TestCase):
    """A path this script would write that is a directory, or sits under
    a file, is refused with one line and the JSON result — never an
    IsADirectoryError or NotADirectoryError traceback, on a dry run or a
    real one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _assert_refused(self, *args: str) -> None:
        for flags in ((), ("--dry-run",)):
            result, data = run_json("--cwd", str(self.cwd), *args, *flags)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("adopt.py:", result.stderr)
            self.assertIsNotNone(data)
            self.assertFalse(data["changed"])
            self.assertFalse(data["configWritten"])
            self.assertFalse(data["claudeMdWritten"])

    def test_claude_md_that_is_a_directory_is_refused(self) -> None:
        (self.cwd / "CLAUDE.md").mkdir()
        self._assert_refused()
        self.assertFalse((self.cwd / ".claude").exists(), "the config is not written either")

    def test_dot_claude_that_is_a_file_is_refused(self) -> None:
        (self.cwd / ".claude").write_text("not a directory\n", encoding="utf-8")
        self._assert_refused()
        self.assertFalse((self.cwd / "CLAUDE.md").exists())

    def test_config_path_that_is_a_directory_is_refused(self) -> None:
        (self.cwd / ".claude" / "promise.config.json").mkdir(parents=True)
        self._assert_refused()

    def test_non_utf8_claude_md_is_refused_with_json_on_stdout(self) -> None:
        (self.cwd / "CLAUDE.md").write_bytes(b"\xff\xfe\x00# notes\x00")
        self._assert_refused()
        self.assertEqual((self.cwd / "CLAUDE.md").read_bytes(), b"\xff\xfe\x00# notes\x00")


if __name__ == "__main__":
    unittest.main()
