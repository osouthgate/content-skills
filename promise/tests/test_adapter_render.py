"""Tests for the promise skill's adapter.py and render_outcome.py scripts.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Scripts and fixtures are located relative to this file, not the current
working directory, so the suite passes regardless of where it is invoked
from — the same convention test_scripts.py uses for the sibling scripts.
Every script is exercised as a subprocess: the real, documented CLI
contract (argv, stdout, stderr, exit code), not imported and called
in-process.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "adapter"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

ADAPTER = SCRIPTS_DIR / "adapter.py"
RENDER = SCRIPTS_DIR / "render_outcome.py"

FIXTURE_SCRIPTS_DIR = FIXTURES_DIR / "scripts"
MINIREPO = FIXTURES_DIR / "minirepo"

# A feedback-shaped string carrying a quote that would close early if this
# were ever composed into a shell command instead of passed as one argv
# element, followed by a command that WOULD create MARKER if a shell ever
# ran it. `touch`, not a mere `echo`, so the marker's absence later is real
# evidence — a payload whose worst case only prints something (as a bare
# `echo PWNED` does — it prints, it does not create a file called PWNED)
# would make that absence prove nothing either way.
MARKER = MINIREPO / "PWNED"
HOSTILE_QUERY = f'"; touch {MARKER}; echo "'


def run(script: Path, *args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def write_config(project_dir: Path, config: dict) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def fixture_command(name: str, *extra_args: str) -> str:
    """A shlex-safe ``<python3> <abs path to fixtures/adapter/scripts/name>`` string."""
    parts = [shlex.quote(sys.executable), shlex.quote(str(FIXTURE_SCRIPTS_DIR / name))]
    parts.extend(shlex.quote(a) for a in extra_args)
    return " ".join(parts)


class ScriptsExistTests(unittest.TestCase):
    def test_scripts_exist(self):
        for path in (ADAPTER, RENDER):
            self.assertTrue(path.is_file(), f"missing script: {path}")

    def test_help_works_and_exits_zero(self):
        for path in (ADAPTER, RENDER):
            result = run(path, "-h")
            self.assertEqual(result.returncode, 0, f"{path.name} -h: {result.stderr}")
            self.assertIn("usage", result.stdout.lower())


class AdapterShowTests(unittest.TestCase):
    """``show`` lists commands and runs nothing.

    Every configured command below points at an executable that does not
    exist. If ``show`` ever actually ran one, the process would exit 127
    (or at least print something to stderr) instead of exiting 0 with
    stderr empty — so a clean exit 0 here is itself proof nothing ran, on
    top of the fact that ``show`` prints command strings, never a result.
    """

    def test_lists_every_configured_command_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(
                project,
                {
                    "commands": {
                        "typeCheck": "does-not-exist-typecheck",
                        "test": "does-not-exist-test",
                        "lint": None,
                    },
                    "map": {
                        "find": "does-not-exist-find",
                        "row": "does-not-exist-row",
                        "checks": ["does-not-exist-check-0", "does-not-exist-check-1"],
                    },
                },
            )
            result = run(ADAPTER, "--cwd", str(project), "show")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertIn("map.find: does-not-exist-find", result.stdout)
            self.assertIn("map.row: does-not-exist-row", result.stdout)
            self.assertIn("map.checks[0]: does-not-exist-check-0", result.stdout)
            self.assertIn("map.checks[1]: does-not-exist-check-1", result.stdout)
            self.assertIn("commands.typeCheck: does-not-exist-typecheck", result.stdout)
            self.assertIn("commands.test: does-not-exist-test", result.stdout)
            # never configured (nextId) or explicitly null (lint) -> never listed
            self.assertNotIn("map.nextId", result.stdout)
            self.assertNotIn("commands.lint", result.stdout)

    def test_show_ignores_json_flag_and_still_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {"find": "does-not-exist"}})
            result = run(ADAPTER, "--cwd", str(project), "--json", "show")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("map.find: does-not-exist", result.stdout)


class AdapterFindTests(unittest.TestCase):
    """A hostile query travels to the child as exactly one argv element."""

    def test_payload_is_a_genuine_positive_control(self):
        # Before trusting MARKER's absence as proof of safety in the two
        # tests below, prove the payload really would create it under a
        # real shell — a payload that could never create the marker (an
        # unmatched quote, or a command that only prints, as the original
        # `echo PWNED` did) would make that proof vacuous.
        self.addCleanup(lambda: MARKER.unlink(missing_ok=True))
        self.assertFalse(MARKER.exists())
        subprocess.run(f'true "{HOSTILE_QUERY}"', shell=True)
        self.assertTrue(
            MARKER.exists(),
            "the payload must be able to create the marker under a real shell, "
            "or its absence later proves nothing",
        )

    def test_hostile_query_arrives_verbatim_as_one_argument(self):
        self.addCleanup(lambda: MARKER.unlink(missing_ok=True))
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "find", HOSTILE_QUERY)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["op"], "find")
        self.assertEqual(data["exit"], 0)
        # adapter's own report of what it ran: the query is the LAST argv
        # element, and only one element carries it.
        self.assertEqual(data["argv"][-1], HOSTILE_QUERY)
        self.assertEqual(data["argv"].count(HOSTILE_QUERY), 1)
        # the child (a fixture that prints repr(sys.argv[1:])) received it
        # as a single-element list, not split or expanded by anything.
        self.assertEqual(data["stdout"], repr([HOSTILE_QUERY]) + "\n")
        self.assertFalse(MARKER.exists(), "the hostile query's shell metacharacters must never reach a shell")

    def test_nothing_the_query_names_is_ever_executed(self):
        self.addCleanup(lambda: MARKER.unlink(missing_ok=True))
        result = run(ADAPTER, "--cwd", str(MINIREPO), "find", HOSTILE_QUERY)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(MARKER.exists(), "the hostile query's shell metacharacters must never reach a shell")

    def test_missing_map_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ADAPTER, "--cwd", tmp, "find", "whatever")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("no map configured", result.stderr)
            self.assertEqual(result.stdout, "")

    def test_missing_map_is_exit_2_under_json_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ADAPTER, "--cwd", tmp, "--json", "find", "whatever")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")  # a refusal is never JSON — nothing ran to report

    def test_map_present_but_find_not_configured_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {"row": "echo hi"}})
            result = run(ADAPTER, "--cwd", str(project), "find", "whatever")
            self.assertEqual(result.returncode, 2)
            self.assertIn("map.find", result.stderr)


class AdapterRowTests(unittest.TestCase):
    def test_valid_id_runs_and_id_is_the_appended_argument(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "row", "C207")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["argv"][-1], "C207")

    def test_id_failing_row_id_pattern_refuses_without_running(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "row", "not-an-id")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        # echo_args.py (map.row's fixture command) would have printed a
        # repr(...) line; an empty stdout is direct evidence it never ran.
        self.assertEqual(result.stdout, "")
        self.assertIn("rowIdPattern", result.stderr)

    def test_id_failing_row_id_pattern_refuses_under_json_too(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "row", "not-an-id")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")


class AdapterNextIdTests(unittest.TestCase):
    def test_runs_with_no_extra_argument(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "next-id")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["op"], "next-id")
        # just [python3, echo_args.py] -- nothing appended
        self.assertEqual(len(data["argv"]), 2)
        self.assertEqual(data["stdout"], "[]\n")


class AdapterChecksTests(unittest.TestCase):
    def test_stops_at_first_failing_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            marker = project / "ran.marker"
            write_config(
                project,
                {
                    "map": {
                        "checks": [
                            fixture_command("ok.py"),
                            fixture_command("fail.py"),
                            fixture_command("touch_marker.py", str(marker)),
                        ]
                    }
                },
            )
            result = run(ADAPTER, "--cwd", str(project), "--json", "checks")
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(len(data), 2, "the third check must never have been attempted")
            self.assertEqual(data[0]["exit"], 0)
            self.assertEqual(data[1]["exit"], 3)
            self.assertFalse(marker.exists(), "the third (skipped) check must never run")

    def test_all_passing_runs_every_check(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "checks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 2)
        self.assertTrue(all(d["exit"] == 0 for d in data))

    def test_missing_checks_key_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {"find": "echo hi"}})
            result = run(ADAPTER, "--cwd", str(project), "checks")
            self.assertEqual(result.returncode, 2)
            self.assertIn("map.checks", result.stderr)


class AdapterVerifyTests(unittest.TestCase):
    def test_runs_typecheck_test_lint_in_order(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "verify")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([d["op"] for d in data], ["typeCheck", "test", "lint"])

    def test_skips_null_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(
                project,
                {"commands": {"typeCheck": None, "test": fixture_command("ok.py"), "lint": None}},
            )
            result = run(ADAPTER, "--cwd", str(project), "--json", "verify")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual([d["op"] for d in data], ["test"])

    def test_no_commands_configured_is_a_trivial_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ADAPTER, "--cwd", tmp, "--json", "verify")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), [])


class AdapterExecutableNotFoundTests(unittest.TestCase):
    def test_not_found_executable_is_exit_127_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {"find": "definitely-not-a-real-executable-xyz123"}})
            result = run(ADAPTER, "--cwd", str(project), "--json", "find", "hello")
            self.assertEqual(result.returncode, 127, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["exit"], 127)
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_not_found_in_a_checks_sequence_stops_it_at_127(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(
                project,
                {"map": {"checks": [fixture_command("ok.py"), "definitely-not-a-real-executable-xyz123"]}},
            )
            result = run(ADAPTER, "--cwd", str(project), "--json", "checks")
            self.assertEqual(result.returncode, 127, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data[-1]["exit"], 127)


class AdapterJsonValidityTests(unittest.TestCase):
    """--json output of every op is valid, parseable JSON."""

    def test_find_json_is_a_single_object(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "find", "x")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)
        self.assertEqual(set(data.keys()), {"op", "argv", "exit", "stdout", "stderr"})

    def test_row_json_is_a_single_object(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "row", "C1")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)

    def test_next_id_json_is_a_single_object(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "next-id")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)

    def test_checks_json_is_a_list(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "checks")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)

    def test_verify_json_is_a_list(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO), "--json", "verify")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)


class AdapterUsageTests(unittest.TestCase):
    def test_no_operation_is_a_usage_error(self):
        result = run(ADAPTER, "--cwd", str(MINIREPO))
        self.assertEqual(result.returncode, 2)

    def test_bad_cwd_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ADAPTER, "--cwd", str(Path(tmp) / "does-not-exist"), "show")
            self.assertEqual(result.returncode, 2)


class RenderOutcomeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        (self.cwd / "docs" / "designs").mkdir(parents=True)

    def render(self, *args: str) -> subprocess.CompletedProcess:
        return run(RENDER, "--cwd", str(self.cwd), "--docs-home", "docs/designs", *args)

    def test_creates_file_with_substitutions_and_leaves_other_placeholders(self):
        result = self.render("--title", "Channel Muting", "--owner", "Ana Smith", "--date", "2026-01-01")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("wrote", result.stdout)

        dest = self.cwd / "docs" / "designs" / "channel-muting.md"
        self.assertTrue(dest.is_file())
        text = dest.read_text(encoding="utf-8")

        self.assertTrue(text.startswith("# Channel Muting\n"))
        self.assertIn("Owner: Ana Smith        Last decision: 2026-01-01", text)
        self.assertIn(
            "*(author: Ana Smith, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*",
            text,
        )

        # every other placeholder is untouched
        self.assertIn("<one line — what is true after this ships>", text)
        self.assertIn("<rule — one line, stated as a fact, verbatim>", text)
        self.assertIn("Supersedes: —", text)
        self.assertIn("Qn — owner: <name> — BLOCKING | non-blocking", text)

        # newline="\n" + utf-8, regardless of platform
        raw = dest.read_bytes()
        self.assertNotIn(b"\r\n", raw)

    def test_default_date_is_today_iso_form(self):
        result = self.render("--title", "No Date Given", "--owner", "Ana")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (self.cwd / "docs" / "designs" / "no-date-given.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"Last decision: \d{4}-\d{2}-\d{2}")

    def test_refuses_to_overwrite_an_existing_file(self):
        first = self.render("--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01")
        self.assertEqual(first.returncode, 0)
        before = (self.cwd / "docs" / "designs" / "channel-muting.md").read_text(encoding="utf-8")

        second = self.render("--title", "Channel Muting", "--owner", "Someone Else", "--date", "2026-02-02")
        self.assertEqual(second.returncode, 2, second.stdout + second.stderr)
        self.assertIn("channel-muting.md", second.stderr)
        self.assertIn("already exists", second.stderr)

        after = (self.cwd / "docs" / "designs" / "channel-muting.md").read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_dry_run_prints_rendered_text_and_writes_nothing(self):
        result = self.render("--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("# Channel Muting", result.stdout)
        self.assertIn("Owner: Ana        Last decision: 2026-01-01", result.stdout)
        self.assertFalse((self.cwd / "docs" / "designs" / "channel-muting.md").exists())

    def test_dry_run_refuses_when_destination_already_exists(self):
        self.render("--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01")
        result = self.render("--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01", "--dry-run")
        self.assertEqual(result.returncode, 2)

    def test_json_reports_path_written_slug(self):
        result = self.render("--title", "Channel Muting", "--owner", "Ana", "--date", "2026-01-01", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data.keys()), {"path", "written", "slug"})
        self.assertTrue(data["written"])
        self.assertEqual(data["slug"], "channel-muting")
        self.assertTrue(data["path"].endswith("channel-muting.md"))
        self.assertTrue(Path(data["path"]).is_file())

    def test_dry_run_json_reports_written_false_and_writes_nothing(self):
        result = self.render("--title", "Channel Muting", "--owner", "Ana", "--dry-run", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data["written"])
        self.assertEqual(data["slug"], "channel-muting")
        self.assertFalse((self.cwd / "docs" / "designs" / "channel-muting.md").exists())

    def test_missing_docs_home_is_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(RENDER, "--cwd", tmp, "--title", "Foo", "--owner", "Ana")
            self.assertEqual(result.returncode, 2)
            self.assertIn("no docs home", result.stderr)
            self.assertIn("--docs-home", result.stderr)

    def test_docs_home_from_orient_config_when_flag_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs" / "rfcs").mkdir(parents=True)
            claude_dir = project / ".claude"
            claude_dir.mkdir()
            (claude_dir / "promise.config.json").write_text(
                json.dumps({"docsHome": "docs/rfcs"}), encoding="utf-8"
            )
            result = run(RENDER, "--cwd", str(project), "--title", "From Config", "--owner", "Ana", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertTrue(data["path"].replace("\\", "/").endswith("docs/rfcs/from-config.md"))


class RenderOutcomeSlugTests(unittest.TestCase):
    """Slug rules: spaces, punctuation and unicode — checked via --dry-run --json
    so no file is ever written."""

    def slug_of(self, title: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                RENDER,
                "--cwd",
                tmp,
                "--docs-home",
                "docs/designs",
                "--title",
                title,
                "--owner",
                "Ana",
                "--dry-run",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)["slug"]

    def test_spaces_become_hyphens(self):
        self.assertEqual(self.slug_of("Channel Muting"), "channel-muting")

    def test_mixed_case_is_lowered(self):
        self.assertEqual(self.slug_of("ChAnNeL MuTiNg"), "channel-muting")

    def test_punctuation_runs_collapse_to_a_single_hyphen(self):
        self.assertEqual(self.slug_of("Wording!! Quarrel??"), "wording-quarrel")

    def test_leading_and_trailing_noise_is_trimmed(self):
        self.assertEqual(self.slug_of("  -- Spaced Out --  "), "spaced-out")

    def test_digits_are_kept(self):
        self.assertEqual(self.slug_of("3D Printing v2"), "3d-printing-v2")

    def test_unicode_letters_collapse_like_punctuation(self):
        self.assertEqual(self.slug_of("Café Menu"), "caf-menu")


if __name__ == "__main__":
    unittest.main()
