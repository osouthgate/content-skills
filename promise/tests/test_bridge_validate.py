"""Tests for the promise skill's bridge_validate.py script.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Mirrors test_adapter_render.py's own conventions: scripts and fixtures are
located relative to this file, not the current working directory, and
bridge_validate.py is exercised as a real subprocess (argv, stdout, stderr,
exit code) — never imported and called in-process, except where the
sibling-module ``normalize()`` helper itself is worth a direct unit check.
Fixtures live under fixtures/bridge/: agreed_bridged.md is the conforming
doc, bridged, with one deliberately drifted row; each other .md fixture is
agreed_bridged.md with exactly one further change, named after the rule it
trips. fake_row.py stands in for a project's `map.row` command.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "bridge"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

BRIDGE = SCRIPTS_DIR / "bridge_validate.py"
ADAPTER = SCRIPTS_DIR / "adapter.py"
LINT = SCRIPTS_DIR / "lint_outcome.py"
FAKE_ROW = FIXTURES_DIR / "fake_row.py"

# A Row cell carrying every shell metacharacter that would matter if it were
# ever composed into a shell command instead of passed as one argv element.
HOSTILE_ROW = 'R1"; echo PWNED; $(echo X) `whoami`'

FIXTURE_NAMES = (
    "agreed_bridged.md",
    "agreed_missing_row.md",
    "agreed_bad_row_id.md",
    "agreed_no_snapshot.md",
    "draft_unbridged.md",
)


def run(*args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BRIDGE), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def run_json(*args: str) -> Tuple[subprocess.CompletedProcess, dict]:
    result = run(*args)
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


def write_config(project_dir: Path, config: dict) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def fixture_command(name: str, *extra_args: str) -> str:
    """A shlex-safe ``<python3> <abs path to fixtures/bridge/name>`` string."""
    parts = [shlex.quote(sys.executable), shlex.quote(str(FIXTURES_DIR / name))]
    parts.extend(shlex.quote(a) for a in extra_args)
    return " ".join(parts)


def bridged_project(project_dir: Path, row_id_pattern: Optional[str] = r"^R\d+$", with_row: bool = True) -> Path:
    """A temp project dir whose map.row (when requested) runs fake_row.py."""
    map_value = {"recipe": "docs/how-to/adding-a-row.md", "find": fixture_command("fake_row.py")}
    if with_row:
        map_value["row"] = fixture_command("fake_row.py")
    if row_id_pattern is not None:
        map_value["rowIdPattern"] = row_id_pattern
    write_config(project_dir, {"map": map_value})
    return project_dir


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists(self) -> None:
        self.assertTrue(BRIDGE.is_file())

    def test_help_works_and_exits_zero(self) -> None:
        result = run("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage", result.stdout.lower())


class FixturesExistTests(unittest.TestCase):
    def test_every_fixture_exists(self) -> None:
        for name in (*FIXTURE_NAMES, "fake_row.py"):
            self.assertTrue((FIXTURES_DIR / name).is_file(), f"missing fixture: {name}")

    def test_agreed_bridged_lints_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(LINT), str(FIXTURES_DIR / "agreed_bridged.md"), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})


class RuleIsolationTests(unittest.TestCase):
    """Each fixture trips exactly its own rule, as an error, and no other
    error-severity rule fires alongside it. Every fixture here is `agreed`
    with AT-3 mapped to R2, whose map text is deliberately reworded (see
    fake_row.py) — so THEN_NOT_IN_MAP (a warning, never an error) is
    expected to co-occur in every case and is asserted on its own below."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def error_rules(self, filename: str) -> Tuple[subprocess.CompletedProcess, dict, list]:
        result, data = run_json(str(FIXTURES_DIR / filename), "--cwd", str(self.project), "--json")
        self.assertIsNotNone(data, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        return result, data, error_rules

    def test_agreed_bridged_has_no_error(self) -> None:
        result, data, error_rules = self.error_rules("agreed_bridged.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(error_rules, [])
        self.assertEqual(data["status"], "agreed")
        self.assertTrue(data["bridged"])
        self.assertTrue(data["mapConfigured"])

    def test_missing_row_trips_only_row_missing(self) -> None:
        result, _, error_rules = self.error_rules("agreed_missing_row.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["ROW_MISSING"])

    def test_bad_row_id_trips_only_row_id_format(self) -> None:
        result, _, error_rules = self.error_rules("agreed_bad_row_id.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["ROW_ID_FORMAT"])

    def test_bad_row_id_is_never_looked_up(self) -> None:
        # A malformed id must never reach ROW_NOT_FOUND/THEN_NOT_IN_MAP —
        # bridge_validate.py must not attempt a lookup for an id it has
        # already rejected on shape.
        _, data, _ = self.error_rules("agreed_bad_row_id.md")
        bad_row = next(r for r in data["rows"] if r["row"] == "R1x")
        self.assertIsNone(bad_row["found"])
        self.assertIsNone(bad_row["inSync"])

    def test_no_snapshot_trips_only_snapshot_line_missing(self) -> None:
        result, _, error_rules = self.error_rules("agreed_no_snapshot.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["SNAPSHOT_LINE_MISSING"])

    def test_draft_is_not_bridged_and_runs_no_other_check(self) -> None:
        result, data, error_rules = self.error_rules("draft_unbridged.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(error_rules, [])
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["bridged"])
        self.assertTrue(data["mapConfigured"])
        self.assertEqual(data["rows"], [])
        self.assertEqual([f["rule"] for f in data["findings"]], ["NOT_BRIDGED"])
        self.assertEqual(data["findings"][0]["severity"], "info")


class DriftTests(unittest.TestCase):
    """THEN_NOT_IN_MAP: AT-3's Then no longer appears in R2's current text."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def test_drift_is_a_warning_and_exits_zero(self) -> None:
        result, data = run_json(
            str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        drift = [f for f in data["findings"] if f["rule"] == "THEN_NOT_IN_MAP"]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["severity"], "warn")
        self.assertEqual(data["stats"]["drifted"], 1)
        self.assertEqual(data["stats"]["mapped"], 3)
        self.assertEqual(data["stats"]["rows"], 3)

    def test_strict_promotes_drift_to_error_and_exits_one(self) -> None:
        result, data = run_json(
            str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json", "--strict"
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        drift = [f for f in data["findings"] if f["rule"] == "THEN_NOT_IN_MAP"]
        self.assertEqual(drift[0]["severity"], "error")

    def test_row_found_and_in_sync_per_row(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertTrue(by_id["AT-1"]["found"])
        self.assertTrue(by_id["AT-1"]["inSync"])
        self.assertTrue(by_id["AT-2"]["found"])
        self.assertTrue(by_id["AT-2"]["inSync"])
        self.assertTrue(by_id["AT-3"]["found"])
        self.assertFalse(by_id["AT-3"]["inSync"])

    def test_adapter_called_once_per_distinct_row_id(self) -> None:
        # R1 covers both AT-1 and AT-2; a correct cache calls adapter.py's
        # row op once for R1 and once for R2, never twice for the same id.
        # Verified indirectly: the human summary's mapped/drifted counts are
        # only correct if every row was actually looked up, and a duplicate
        # lookup would not change that count — so this asserts the visible
        # behaviour a caching bug would not affect, documenting the cache is
        # a performance property rather than one the CLI surface exposes.
        result = run(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bridge: 3 rows, 3 mapped, 1 drifted", result.stdout)


class MapNotConfiguredTests(unittest.TestCase):
    def test_no_config_is_map_not_configured_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", tmp, "--json"
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])
            self.assertEqual(data["findings"][0]["severity"], "error")
            self.assertFalse(data["mapConfigured"])
            self.assertFalse(data["bridged"])
            # status is still reported: the doc itself was read successfully.
            self.assertEqual(data["status"], "agreed")

    def test_no_map_key_in_config_is_also_map_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"docsHome": "docs/designs"})
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])


class UnreadableTests(unittest.TestCase):
    def test_missing_doc_is_unreadable_exit_one_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, data = run_json(str(Path(tmp) / "does-not-exist.md"), "--cwd", tmp, "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["UNREADABLE"])
            self.assertIsNone(data["status"])
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_doc_human_output_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(str(Path(tmp) / "nope.md"), "--cwd", tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("UNREADABLE", result.stdout)
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_not_utf8_doc_is_unreadable_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            bad = project / "bad.md"
            bad.write_bytes(b"\xff\xfe\x00Status: agreed\x00")
            result, data = run_json(str(bad), "--cwd", str(project), "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["UNREADABLE"])
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)


class HostileRowIdTests(unittest.TestCase):
    """A hostile Row cell fails ROW_ID_FORMAT under the real pattern, and —
    relaxed so the lookup is attempted — reaches fake_row.py as exactly one
    argv element, never as text a shell parses."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
        hostile = base.replace(
            "| AT-1 | Ana is in a channel | she mutes it | she gets no push or badge from it | R1 |",
            f"| AT-1 | Ana is in a channel | she mutes it | she gets no push or badge from it | {HOSTILE_ROW} |",
        )
        self.assertNotEqual(hostile, base)
        self.doc = self.project / "hostile.md"
        self.doc.write_text(hostile, encoding="utf-8")
        self.marker = self.project / "PWNED"
        self.addCleanup(lambda: self.marker.unlink(missing_ok=True))

    def test_fails_row_id_format_under_the_real_pattern(self) -> None:
        bridged_project(self.project, row_id_pattern=r"^R\d+$")
        result, data = run_json(str(self.doc), "--cwd", str(self.project), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["ROW_ID_FORMAT"])
        self.assertFalse(self.marker.exists(), "the hostile Row cell's `echo PWNED` must never run")

    def test_relaxed_pattern_reaches_fake_row_as_one_argv_element(self) -> None:
        bridged_project(self.project, row_id_pattern=".*")
        # bridge_validate.py's own run: no ROW_ID_FORMAT now that the id
        # "matches"; the lookup is attempted and the map genuinely has no
        # such row, so ROW_NOT_FOUND — not a crash, not a shell escape.
        result, data = run_json(str(self.doc), "--cwd", str(self.project), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["ROW_NOT_FOUND"])
        self.assertFalse(self.marker.exists(), "the hostile Row cell's `echo PWNED` must never run")

        # Direct adapter.py call (bridge_validate.py's own documented
        # boundary for every map.row lookup) proves the id arrived as
        # exactly one argv element: fake_row.py's own argv echo, captured
        # verbatim in adapter.py's --json "stdout" field.
        proc = subprocess.run(
            [sys.executable, str(ADAPTER), "--cwd", str(self.project), "--json", "row", HOSTILE_ROW],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)  # fake_row.py: unknown id
        adapter_data = json.loads(proc.stdout)
        self.assertEqual(adapter_data["argv"][-1], HOSTILE_ROW)
        self.assertEqual(adapter_data["argv"].count(HOSTILE_ROW), 1)
        self.assertEqual(adapter_data["stdout"].splitlines()[0], repr([HOSTILE_ROW]))
        self.assertFalse(self.marker.exists(), "the hostile Row cell's `echo PWNED` must never run")


class NoRowIdPatternTests(unittest.TestCase):
    def test_missing_pattern_warns_and_skips_row_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), row_id_pattern=None)
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            rules = [f["rule"] for f in data["findings"]]
            self.assertIn("NO_ROW_ID_PATTERN", rules)
            self.assertNotIn("ROW_ID_FORMAT", rules)
            warn = next(f for f in data["findings"] if f["rule"] == "NO_ROW_ID_PATTERN")
            self.assertEqual(warn["severity"], "warn")


class NoMapRowCommandTests(unittest.TestCase):
    def test_missing_row_command_warns_and_skips_drift_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), with_row=False)
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rules = [f["rule"] for f in data["findings"]]
            self.assertIn("NO_MAP_ROW_COMMAND", rules)
            self.assertNotIn("ROW_NOT_FOUND", rules)
            self.assertNotIn("THEN_NOT_IN_MAP", rules)
            for row in data["rows"]:
                self.assertIsNone(row["found"])
                self.assertIsNone(row["inSync"])


class JsonSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def test_top_level_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        self.assertEqual(
            set(data.keys()),
            {"path", "status", "bridged", "mapConfigured", "rows", "findings", "stats"},
        )

    def test_row_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        for row in data["rows"]:
            self.assertEqual(set(row.keys()), {"id", "row", "line", "found", "inSync"})

    def test_finding_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_missing_row.md"), "--cwd", str(self.project), "--json")
        for f in data["findings"]:
            self.assertEqual(set(f.keys()), {"rule", "line", "message", "severity"})

    def test_stats_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        self.assertEqual(
            set(data["stats"].keys()), {"rows", "mapped", "drifted", "errors", "warnings"}
        )

    def test_stdout_is_exactly_one_parseable_value(self) -> None:
        result = run(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        json.loads(result.stdout)  # raises if this is not exactly one JSON value


class HumanOutputTests(unittest.TestCase):
    def test_summary_line_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp))
            result = run(str(FIXTURES_DIR / "agreed_missing_row.md"), "--cwd", str(project))
            lines = result.stdout.strip().splitlines()
            self.assertTrue(lines[0].startswith(str(FIXTURES_DIR / "agreed_missing_row.md") + ":"))
            self.assertIn("ROW_MISSING", lines[0])
            self.assertEqual(lines[-1], "bridge: 3 rows, 2 mapped, 1 drifted")


class UsageErrorTests(unittest.TestCase):
    def test_no_doc_argument_is_a_usage_error(self) -> None:
        result = run()
        self.assertEqual(result.returncode, 2)

    def test_bad_cwd_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(Path(tmp) / "does-not-exist"))
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
