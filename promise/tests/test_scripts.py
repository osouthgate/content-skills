"""Tests for the promise skill's scripts (orient, lint_outcome, outcome_rows, adopt).

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Scripts and fixtures are located relative to this file, not the current
working directory, so the suite passes regardless of where it is invoked
from. Every script is exercised as a subprocess (the real, documented
CLI contract — argv, stdout, stderr, exit code), not imported and called
in-process, except where sibling-script import itself is under test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

ORIENT = SCRIPTS_DIR / "orient.py"
LINT = SCRIPTS_DIR / "lint_outcome.py"
ROWS = SCRIPTS_DIR / "outcome_rows.py"
ADOPT = SCRIPTS_DIR / "adopt.py"

# One fixture per error-severity rule in architecture.md SS9. Each fixture is
# conforming.md with exactly one change, named after the rule it trips.
ERROR_RULE_FIXTURES = {
    "HEADER_STATUS": "header_status.md",
    "HEADER_OWNER": "header_owner.md",
    "CONTENTS_LINE": "contents_line.md",
    "HEADINGS_BARE": "headings_bare.md",
    "TLDR_BUDGET": "tldr_budget.md",
    "TLDR_FIELDS": "tldr_fields.md",
    "RULES_FORMAT": "rules_format.md",
    "RULES_TAGGED": "rules_tagged.md",
    "TAGS_RESOLVE": "tags_resolve.md",
    "AT_IDS_UNIQUE": "at_ids_unique.md",
    "SCENARIOS_COUNT": "scenarios_count.md",
    "WHY_LINE": "why_line.md",
    "UNTESTED_ON_AGREED": "untested_on_agreed.md",
    "PLACEHOLDER": "placeholder.md",
}


def run(script: Path, *args: str, cwd: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def orientation_of(cwd: str, mode: str = None) -> dict:
    args = ["--cwd", cwd]
    if mode is not None:
        args += ["--mode", mode]
    result = run(ORIENT, *args)
    return json.loads(result.stdout)


class ScriptsExistTests(unittest.TestCase):
    def test_all_four_scripts_exist(self):
        for path in (ORIENT, LINT, ROWS, ADOPT):
            self.assertTrue(path.is_file(), f"missing script: {path}")

    def test_help_works_and_exits_zero(self):
        for path in (ORIENT, LINT, ROWS, ADOPT):
            result = run(path, "-h")
            self.assertEqual(result.returncode, 0, f"{path.name} -h: {result.stderr}")
            self.assertIn("usage", result.stdout.lower())


class LintConformingTests(unittest.TestCase):
    def setUp(self):
        self.path = str(FIXTURES_DIR / "conforming.md")

    def test_exits_zero_with_zero_findings(self):
        result = run(LINT, self.path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_json_has_zero_findings_including_zero_warnings(self):
        result = run(LINT, self.path, "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_strict_still_exits_zero(self):
        result = run(LINT, self.path, "--strict")
        self.assertEqual(result.returncode, 0)


class LintErrorRuleFixtureTests(unittest.TestCase):
    """Each violation fixture is conforming.md with exactly one change: the
    named rule fires, and no OTHER error-severity rule fires alongside it."""

    def test_every_error_rule_fixture_exists(self):
        for rule, filename in ERROR_RULE_FIXTURES.items():
            self.assertTrue((FIXTURES_DIR / filename).is_file(), f"missing fixture for {rule}: {filename}")

    def test_each_fixture_trips_only_its_rule(self):
        for rule, filename in ERROR_RULE_FIXTURES.items():
            with self.subTest(rule=rule, fixture=filename):
                result = run(LINT, str(FIXTURES_DIR / filename), "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                data = json.loads(result.stdout)
                error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
                self.assertEqual(
                    error_rules,
                    [rule],
                    f"{filename}: expected only {rule} to fire as an error, got {error_rules}",
                )
                self.assertTrue(
                    any(f["rule"] == rule for f in data["findings"]),
                    f"{filename}: {rule} did not fire at all",
                )

    def test_human_output_matches_path_line_rule_message_format(self):
        result = run(LINT, str(FIXTURES_DIR / "header_status.md"))
        self.assertEqual(result.returncode, 1)
        line = result.stdout.strip().splitlines()[0]
        self.assertIn(":", line)
        self.assertIn("HEADER_STATUS", line)
        self.assertTrue(line.startswith(str(FIXTURES_DIR / "header_status.md")))


class LintStrictPromotionTests(unittest.TestCase):
    def setUp(self):
        self.path = str(FIXTURES_DIR / "agent_notes_many.md")

    def test_warn_only_fixture_exits_zero_without_strict(self):
        result = run(LINT, self.path, "--json")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["stats"]["errors"], 0)
        self.assertGreaterEqual(data["stats"]["warnings"], 1)
        self.assertTrue(any(f["rule"] == "AGENT_NOTES_MANY" for f in data["findings"]))

    def test_strict_promotes_warn_to_error_and_exits_one(self):
        result = run(LINT, self.path, "--strict", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        agent_notes = [f for f in data["findings"] if f["rule"] == "AGENT_NOTES_MANY"]
        self.assertTrue(agent_notes)
        self.assertEqual(agent_notes[0]["severity"], "error")
        self.assertEqual(data["stats"]["errors"], data["stats"]["total"])


class LintUsageTests(unittest.TestCase):
    def test_missing_path_is_usage_error(self):
        result = run(LINT, str(FIXTURES_DIR / "does-not-exist.md"))
        self.assertEqual(result.returncode, 2)


class OutcomeRowsTests(unittest.TestCase):
    def setUp(self):
        self.path = str(FIXTURES_DIR / "conforming.md")

    def test_round_trips_conforming_fixture(self):
        result = run(ROWS, self.path, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)

        self.assertEqual(data["status"], "draft")

        self.assertEqual(len(data["rules"]), 2)
        self.assertEqual(data["rules"][0]["tags"], ["AT-1", "AT-2"])
        self.assertEqual(data["rules"][1]["tags"], ["UNTESTED"])
        self.assertTrue(data["rules"][0]["text"].startswith("A muted channel"))

        self.assertEqual([r["id"] for r in data["rows"]], ["AT-1", "AT-2", "AT-3"])
        self.assertTrue(all(r["row"] is None for r in data["rows"]))
        self.assertEqual(data["rows"][0]["given"], "Ana is in a channel")
        self.assertEqual(data["rows"][0]["when"], "she mutes it")
        self.assertEqual(data["rows"][0]["then"], "she gets no push or badge from it")

        self.assertEqual(
            data["signal"],
            "Ana mutes a busy channel and gets zero notifications from it "
            "for a day, then unmutes and notifications resume.",
        )

    def test_human_output_is_a_table_not_json(self):
        result = run(ROWS, self.path)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("{", result.stdout.split("\n")[0])
        self.assertIn("AT-1", result.stdout)
        self.assertIn("Signal:", result.stdout)

    def test_missing_file_is_usage_error(self):
        result = run(ROWS, str(FIXTURES_DIR / "does-not-exist.md"))
        self.assertEqual(result.returncode, 2)


class OrientEmptyDirTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def test_every_schema_key_present_and_exit_zero(self):
        result = run(ORIENT, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        expected_keys = {
            "skillDir", "cwd", "mode", "frameworkPath", "frameworkSource",
            "config", "docsHome", "docsHomeSource", "plansFolder", "commands",
            "map", "claudeMd", "adopted", "existingDocs", "warnings",
            "suggestedMode", "signals",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    def test_docs_home_null_commands_null_source_none(self):
        data = orientation_of(self.cwd)
        self.assertIsNone(data["docsHome"])
        self.assertEqual(data["docsHomeSource"], "none")
        self.assertIsNone(data["commands"]["typeCheck"])
        self.assertIsNone(data["commands"]["test"])
        self.assertIsNone(data["commands"]["lint"])
        self.assertEqual(data["commands"]["source"], "none")

    def test_at_least_one_warning_and_not_adopted(self):
        data = orientation_of(self.cwd)
        self.assertGreaterEqual(len(data["warnings"]), 1)
        self.assertFalse(data["adopted"])
        self.assertFalse(data["config"]["loaded"])
        self.assertIsNone(data["config"]["path"])
        self.assertEqual(data["config"]["raw"], {})
        self.assertIsNone(data["map"])
        self.assertEqual(data["existingDocs"], [])

    def test_framework_source_is_bundled(self):
        data = orientation_of(self.cwd)
        self.assertEqual(data["frameworkSource"], "bundled")
        self.assertTrue(Path(data["frameworkPath"]).is_file())

    def test_never_emits_to_stderr_on_success(self):
        result = run(ORIENT, "--cwd", self.cwd)
        self.assertEqual(result.stderr, "")

    def test_mode_defaults_to_new(self):
        data = orientation_of(self.cwd)
        self.assertEqual(data["mode"], "new")

    def test_mode_infer_for_unrecognised_word(self):
        data = orientation_of(self.cwd, mode="frobnicate")
        self.assertEqual(data["mode"], "infer")

    def test_mode_echoed_for_recognised_word(self):
        data = orientation_of(self.cwd, mode="reconcile")
        self.assertEqual(data["mode"], "reconcile")


class OrientMinirepoTests(unittest.TestCase):
    def setUp(self):
        self.cwd = str(FIXTURES_DIR / "minirepo")

    def test_config_source_and_raw_map_verbatim(self):
        data = orientation_of(self.cwd)
        self.assertTrue(data["config"]["loaded"])
        self.assertTrue(data["config"]["path"].endswith(".claude/promise.config.json"))
        self.assertEqual(data["docsHomeSource"], "config")
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertEqual(data["commands"]["source"], "config")
        self.assertEqual(data["commands"]["typeCheck"], "pnpm type-check")

        expected_map = json.loads((Path(self.cwd) / ".claude" / "promise.config.json").read_text())["map"]
        self.assertEqual(data["map"], expected_map)

    def test_existing_doc_reported_with_status_and_title(self):
        data = orientation_of(self.cwd)
        self.assertEqual(len(data["existingDocs"]), 1)
        doc = data["existingDocs"][0]
        self.assertEqual(doc["path"], "docs/designs/one.md")
        self.assertEqual(doc["title"], "Channel muting")
        self.assertEqual(doc["status"], "draft")
        self.assertEqual(doc["lastDecision"], "2026-01-01")

    def test_never_emits_to_stderr_on_success(self):
        result = run(ORIENT, "--cwd", self.cwd)
        self.assertEqual(result.stderr, "")


class JsonValidityTests(unittest.TestCase):
    """--json output of every script is valid, parseable JSON."""

    def test_orient_json_is_valid(self):
        result = run(ORIENT, "--cwd", str(FIXTURES_DIR / "minirepo"))
        json.loads(result.stdout)  # raises on invalid JSON

    def test_lint_single_file_json_is_valid_object(self):
        result = run(LINT, str(FIXTURES_DIR / "conforming.md"), "--json")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, dict)
        self.assertIn("findings", data)

    def test_lint_directory_json_is_valid_array(self):
        result = run(LINT, str(FIXTURES_DIR / "minirepo" / "docs" / "designs"), "--json")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("findings", data[0])

    def test_outcome_rows_json_is_valid(self):
        result = run(ROWS, str(FIXTURES_DIR / "conforming.md"), "--json")
        json.loads(result.stdout)

    def test_adopt_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ADOPT, "--cwd", tmp, "--dry-run")
            data = json.loads(result.stdout)
            self.assertEqual(
                set(data.keys()),
                {"configWritten", "configPath", "claudeMdWritten", "claudeMdPath", "changed", "dryRun"},
            )


class AdoptTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def test_dry_run_writes_nothing_and_reports_dry_run_true(self):
        result = run(ADOPT, "--cwd", self.cwd, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["dryRun"])
        self.assertFalse(data["configWritten"])
        self.assertFalse(data["claudeMdWritten"])
        self.assertEqual(list(Path(self.cwd).iterdir()), [])

    def test_first_run_creates_config_and_claude_md(self):
        result = run(ADOPT, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["configWritten"])
        self.assertTrue(data["claudeMdWritten"])
        self.assertTrue(data["changed"])

        config_path = Path(self.cwd) / ".claude" / "promise.config.json"
        claude_md_path = Path(self.cwd) / "CLAUDE.md"
        self.assertTrue(config_path.is_file())
        self.assertTrue(claude_md_path.is_file())

        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertIsNone(config["map"])
        self.assertIn("$comment", config)

        claude_md_text = claude_md_path.read_text(encoding="utf-8")
        self.assertTrue(claude_md_text.startswith("<!-- promise:begin"))
        self.assertTrue(claude_md_text.rstrip("\n").endswith("<!-- promise:end -->"))
        self.assertLessEqual(len(claude_md_text.rstrip("\n").splitlines()), 20)

    def test_second_run_is_byte_identical_no_op(self):
        run(ADOPT, "--cwd", self.cwd)
        config_path = Path(self.cwd) / ".claude" / "promise.config.json"
        claude_md_path = Path(self.cwd) / "CLAUDE.md"
        config_before = config_path.read_bytes()
        claude_md_before = claude_md_path.read_bytes()

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(data["configWritten"])
        self.assertFalse(data["claudeMdWritten"])
        self.assertFalse(data["changed"])
        self.assertEqual(config_path.read_bytes(), config_before)
        self.assertEqual(claude_md_path.read_bytes(), claude_md_before)

    def test_hand_edited_block_is_restored_content_outside_untouched(self):
        run(ADOPT, "--cwd", self.cwd)
        claude_md_path = Path(self.cwd) / "CLAUDE.md"
        original = claude_md_path.read_text(encoding="utf-8")
        vandalised = (
            "# Project notes\n\nKeep this line.\n\n"
            + original.replace("Say what you want", "VANDALISED TEXT")
            + "\n## Trailer\nKeep this too.\n"
        )
        claude_md_path.write_text(vandalised, encoding="utf-8")

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertTrue(data["claudeMdWritten"])
        self.assertTrue(data["changed"])

        restored = claude_md_path.read_text(encoding="utf-8")
        self.assertIn("Keep this line.", restored)
        self.assertIn("Keep this too.", restored)
        self.assertNotIn("VANDALISED TEXT", restored)
        self.assertIn("Say what you want", restored)

    def test_missing_claude_md_is_created_at_project_root(self):
        self.assertFalse((Path(self.cwd) / "CLAUDE.md").exists())
        run(ADOPT, "--cwd", self.cwd)
        self.assertTrue((Path(self.cwd) / "CLAUDE.md").is_file())

    def test_preexisting_config_is_never_overwritten(self):
        claude_dir = Path(self.cwd) / ".claude"
        claude_dir.mkdir(parents=True)
        config_path = claude_dir / "promise.config.json"
        original_text = '{\n  "docsHome": "docs/rfcs",\n  "map": null\n}\n'
        config_path.write_text(original_text, encoding="utf-8")

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertFalse(data["configWritten"])
        self.assertEqual(config_path.read_text(encoding="utf-8"), original_text)

    def test_orient_reports_adopted_true_after_adopt(self):
        run(ADOPT, "--cwd", self.cwd)
        data = orientation_of(self.cwd)
        self.assertTrue(data["adopted"])
        self.assertTrue(data["claudeMd"]["hasPromiseSection"])
        self.assertTrue(data["config"]["loaded"])

    def test_dot_claude_claude_md_detected_when_root_absent(self):
        claude_dir = Path(self.cwd) / ".claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "CLAUDE.md").write_text("# Existing notes\n", encoding="utf-8")

        data = orientation_of(self.cwd)
        self.assertEqual(data["claudeMd"]["path"], str((claude_dir / "CLAUDE.md").resolve()))
        self.assertFalse(data["claudeMd"]["hasPromiseSection"])

        run(ADOPT, "--cwd", self.cwd)
        self.assertFalse((Path(self.cwd) / "CLAUDE.md").exists())
        updated = (claude_dir / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("Existing notes", updated)
        self.assertIn("<!-- promise:begin", updated)

    def test_no_config_flag_skips_config(self):
        result = run(ADOPT, "--cwd", self.cwd, "--no-config")
        data = json.loads(result.stdout)
        self.assertFalse(data["configWritten"])
        self.assertFalse((Path(self.cwd) / ".claude" / "promise.config.json").exists())
        self.assertTrue((Path(self.cwd) / "CLAUDE.md").exists())

    def test_no_claude_md_flag_skips_section(self):
        result = run(ADOPT, "--cwd", self.cwd, "--no-claude-md")
        data = json.loads(result.stdout)
        self.assertFalse(data["claudeMdWritten"])
        self.assertFalse((Path(self.cwd) / "CLAUDE.md").exists())
        self.assertTrue((Path(self.cwd) / ".claude" / "promise.config.json").exists())

    def test_docs_home_flag_recorded_in_fresh_config(self):
        run(ADOPT, "--cwd", self.cwd, "--docs-home", "docs/rfcs")
        config = json.loads((Path(self.cwd) / ".claude" / "promise.config.json").read_text())
        self.assertEqual(config["docsHome"], "docs/rfcs")

    def test_bad_cwd_is_usage_error(self):
        result = run(ADOPT, "--cwd", str(Path(self.cwd) / "does-not-exist"))
        self.assertEqual(result.returncode, 2)


class SecondTableInAcceptance(unittest.TestCase):
    """Only the acceptance table (header cell `#`) is subject to row-id rules. A doc may
    keep other tables in §6 — a classification, a summary — without false findings."""

    def test_other_tables_in_s6_are_ignored(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "lint_outcome.py"), str(FIXTURES_DIR / "second_table_in_s6.md"), "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        data = json.loads(proc.stdout)
        rules = [f["rule"] for f in data["findings"]]
        self.assertNotIn("AT_IDS_UNIQUE", rules, data["findings"])
        self.assertNotIn("TAGS_RESOLVE", rules, data["findings"])
        self.assertEqual(proc.returncode, 0, data["findings"])


if __name__ == "__main__":
    unittest.main()
