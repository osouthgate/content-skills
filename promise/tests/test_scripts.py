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
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
FRAMEWORK = SCRIPTS_DIR.parent / "outcome-framework.md"

ORIENT = SCRIPTS_DIR / "orient.py"
LINT = SCRIPTS_DIR / "lint_outcome.py"
ROWS = SCRIPTS_DIR / "outcome_rows.py"
ADOPT = SCRIPTS_DIR / "adopt.py"

# One fixture per error-severity rule in architecture.md §9. Each fixture is
# conforming.md with exactly one change, named after the rule it trips
# (at_ids_unique.md carries the one mechanically-forced second change: the
# duplicate is a fourth row, so the Scenarios: count moves with it — every
# existing id is cited from §0, so no row could be renamed instead).
ERROR_RULE_FIXTURES = {
    "HEADER_STATUS": "header_status.md",
    "HEADER_OWNER": "header_owner.md",
    "CONTENTS_LINE": "contents_line.md",
    "HEADINGS_BARE": "headings_bare.md",
    "TLDR_BUDGET": "tldr_budget.md",
    "TLDR_FIELDS": "tldr_fields.md",
    "RULES_PRESENT": "rules_present.md",
    "RULES_FORMAT": "rules_format.md",
    "RULES_TAGGED": "rules_tagged.md",
    "TAGS_RESOLVE": "tags_resolve.md",
    "AT_IDS_UNIQUE": "at_ids_unique.md",
    "ACCEPTANCE_ALTITUDE": "acceptance_altitude.md",
    "SCENARIOS_COUNT": "scenarios_count.md",
    "WHY_LINE": "why_line.md",
    "UNTESTED_ON_AGREED": "untested_on_agreed.md",
    "PLACEHOLDER": "placeholder.md",
}

# One fixture per warn-severity rule: it fires as the ONLY finding, the run
# exits 0 without --strict and 1 with it.
WARN_RULE_FIXTURES = {
    "AGENT_NOTES_MANY": "agent_notes_many.md",
    "ALTITUDE_MISSING": "altitude_missing.md",
    "HUMAN_HALF_BUDGET": "human_half_budget.md",
}

# Docs that are conforming.md plus one fenced code block whose contents look
# like structure (a `## 0. TLDR`, a rule bullet, a `## 6.` heading, a table
# row). Each must lint exactly like conforming.md: zero findings.
FENCED_FIXTURES = ("fenced_tldr_before.md", "fenced_heading_in_s5.md")

SECTION_SIGN_DIGRAPH = re.compile(r"\bSS\d")


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


def write_config(cwd: str, config: dict) -> Path:
    """Write cwd/.claude/promise.config.json — the primary location
    orient.py checks first — with the given object."""
    config_dir = Path(cwd) / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "promise.config.json"
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


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


class LintWarnRuleFixtureTests(unittest.TestCase):
    """Each warn fixture is conforming.md with exactly one change: the named
    rule fires as a warning and as the ONLY finding; the run exits 0, and
    --strict promotes it to an error and exits 1."""

    def test_every_warn_rule_fixture_exists(self):
        for rule, filename in WARN_RULE_FIXTURES.items():
            self.assertTrue((FIXTURES_DIR / filename).is_file(), f"missing fixture for {rule}: {filename}")

    def test_warn_only_fixture_exits_zero_without_strict(self):
        for rule, filename in WARN_RULE_FIXTURES.items():
            with self.subTest(rule=rule, fixture=filename):
                result = run(LINT, str(FIXTURES_DIR / filename), "--json")
                data = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(
                    [(f["rule"], f["severity"]) for f in data["findings"]],
                    [(rule, "warn")],
                    f"{filename}: expected {rule} to be the only finding, got {data['findings']}",
                )
                self.assertEqual(data["stats"], {"errors": 0, "warnings": 1, "total": 1})

    def test_strict_promotes_warn_to_error_and_exits_one(self):
        for rule, filename in WARN_RULE_FIXTURES.items():
            with self.subTest(rule=rule, fixture=filename):
                result = run(LINT, str(FIXTURES_DIR / filename), "--strict", "--json")
                data = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [(rule, "error")])
                self.assertEqual(data["stats"]["errors"], data["stats"]["total"])

    def test_human_half_budget_message_names_the_count_and_where_it_stopped(self):
        result = run(LINT, str(FIXTURES_DIR / "human_half_budget.md"), "--json")
        data = json.loads(result.stdout)
        message = data["findings"][0]["message"]
        self.assertIn("(max 150)", message)
        self.assertIn("through the first §3 example", message)

    def test_altitude_missing_message_says_what_to_add(self):
        result = run(LINT, str(FIXTURES_DIR / "altitude_missing.md"), "--json")
        data = json.loads(result.stdout)
        f = data["findings"][0]
        self.assertEqual(f["line"], 78)  # the table's header row
        self.assertIn("no Altitude column", f["message"])
        for value in ("data", "response", "perception", "judgement", "sibling"):
            self.assertIn(value, f["message"])


class FencedBlocksAreIllustrationsTests(unittest.TestCase):
    """A heading, field marker, rule bullet or table row inside a ``` / ~~~
    fence is not structure: the lint, outcome_rows.py and the directory scan
    all read past it."""

    def test_fenced_fixtures_lint_exactly_like_conforming(self):
        for filename in FENCED_FIXTURES:
            with self.subTest(fixture=filename):
                result = run(LINT, str(FIXTURES_DIR / filename), "--json")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["findings"], [])

    def test_fenced_rule_and_table_row_are_not_extracted(self):
        result = run(ROWS, str(FIXTURES_DIR / "fenced_tldr_before.md"), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([r["tags"] for r in data["rules"]], [["AT-1", "AT-2"], ["AT-3"], ["UNTESTED"]])
        self.assertEqual([r["id"] for r in data["rows"]], ["AT-1", "AT-2", "AT-3"])
        self.assertTrue(data["signal"].startswith("Ana mutes a busy channel"))

    def test_fenced_heading_inside_s5_does_not_end_the_section(self):
        # The fence in §5 carries a `## 6. Acceptance` line and a table row:
        # neither a WHY_LINE for §5 nor an extra §6 row may come of it.
        result = run(ROWS, str(FIXTURES_DIR / "fenced_heading_in_s5.md"), "--json")
        data = json.loads(result.stdout)
        self.assertEqual([r["id"] for r in data["rows"]], ["AT-1", "AT-2", "AT-3"])

    def test_lint_and_orient_apply_the_same_fence_rule(self):
        # The fence rule has two homes — lint_outcome.unfenced (used by
        # outcome_rows.py and bridge_validate.py) and orient.unfenced (used
        # by framework_section.py) — because orient imports no sibling.
        # This guard is what keeps them from drifting: identical output on
        # every fixture and on the hand-built edge cases.
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import lint_outcome
            import orient
        finally:
            sys.path.pop(0)
        cases = {}
        for path in sorted(FIXTURES_DIR.rglob("*.md")):
            try:
                cases[str(path.relative_to(FIXTURES_DIR))] = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
        cases["~~~ fence"] = ["# T", "~~~", "## 0. TLDR", "~~~", "## 0. TLDR"]
        cases["indented fence"] = ["# T", "   ```md", "## 0. TLDR", "  ```", "## 1. Problem"]
        cases["unclosed fence"] = ["# T", "```", "## 0. TLDR", "| AT-1 | a | b | c |"]
        cases["fence inside a fence"] = ["```", "```", "## 0. TLDR", "```", "## 6. Acceptance", "```"]
        cases["mixed markers"] = ["```", "~~~", "## 0. TLDR", "```"]
        self.assertGreater(len(cases), 60)
        for name, lines in cases.items():
            with self.subTest(case=name):
                self.assertEqual(lint_outcome.unfenced(lines), orient.unfenced(lines))

    def test_directory_scan_skips_a_framework_copy_in_docs_home_and_a_subfolder(self):
        # The bundled framework shows the template shape only inside a fence
        # (or not at all); copied into docsHome and docsHome/how-to — the
        # example config's own layout — it must not be linted as a doc.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "how-to").mkdir()
            framework_text = FRAMEWORK.read_text(encoding="utf-8")
            (tmp_path / "outcome-framework.md").write_text(framework_text, encoding="utf-8")
            (tmp_path / "how-to" / "outcome-framework.md").write_text(framework_text, encoding="utf-8")
            (tmp_path / "real.md").write_text(
                (FIXTURES_DIR / "fenced_tldr_before.md").read_text(encoding="utf-8"), encoding="utf-8"
            )
            result = run(LINT, tmp, "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual([os.path.basename(r["path"]) for r in data], ["real.md"])


class SectionSignTests(unittest.TestCase):
    """Findings, help text and the docstring print '§', never the digraph
    'SS' (unidecode's transliteration of it)."""

    def _assert_no_digraph(self, text: str, where: str) -> None:
        hit = SECTION_SIGN_DIGRAPH.search(text)
        self.assertIsNone(hit, f"{where}: found {hit.group(0) if hit else ''!r} in {text[:200]!r}")

    def test_no_digraph_in_any_fixture_finding(self):
        for path in sorted(FIXTURES_DIR.glob("*.md")) + sorted((FIXTURES_DIR / "lint-hardening").glob("*.md")):
            result = run(LINT, str(path), "--json")
            self._assert_no_digraph(result.stdout, path.name)

    def test_no_digraph_in_help_or_source(self):
        # Every script, not only the lint: outcome_rows.py and orient.py
        # print section numbers too, and a source-level digraph would reach
        # a message eventually.
        scripts = sorted(SCRIPTS_DIR.glob("*.py"))
        self.assertIn(LINT, scripts)
        for path in scripts:
            with self.subTest(script=path.name):
                help_run = run(path, "-h")
                self.assertEqual(help_run.returncode, 0, help_run.stderr)
                self._assert_no_digraph(help_run.stdout, f"{path.name} -h")
                self._assert_no_digraph(path.read_text(encoding="utf-8"), f"{path.name} source")

    def test_scenarios_count_message_cites_the_section_sign(self):
        result = run(LINT, str(FIXTURES_DIR / "scenarios_count.md"), "--json")
        message = json.loads(result.stdout)["findings"][0]["message"]
        self.assertIn("§6", message)

    def test_findings_survive_a_stdout_that_cannot_encode_the_sign(self):
        # A cp1252 pipe (the Windows default) cannot encode '§', '→' or '—':
        # the run still prints every finding, degraded to '?', and exits 1
        # on the finding rather than dying with UnicodeEncodeError.
        env = dict(os.environ, PYTHONIOENCODING="ascii", PYTHONUTF8="0")
        result = subprocess.run(
            [sys.executable, str(LINT), str(FIXTURES_DIR / "scenarios_count.md")],
            capture_output=True, text=True, env=env, encoding="ascii", errors="replace",
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("SCENARIOS_COUNT", result.stdout)


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

        self.assertEqual(len(data["rules"]), 3)
        self.assertEqual(data["rules"][0]["tags"], ["AT-1", "AT-2"])
        self.assertEqual(data["rules"][1]["tags"], ["AT-3"])
        self.assertEqual(data["rules"][2]["tags"], ["UNTESTED"])
        self.assertTrue(data["rules"][0]["text"].startswith("A muted channel"))

        self.assertEqual([r["id"] for r in data["rows"]], ["AT-1", "AT-2", "AT-3"])
        self.assertTrue(all(r["row"] is None for r in data["rows"]))
        self.assertEqual([r["altitude"] for r in data["rows"]], ["perception"] * 3)
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
            "map", "mapUsable", "claudeMd", "adopted", "existingDocs", "warnings",
            "suggestedMode", "signals", "ambiguous",
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

    def test_mode_is_null_without_the_flag(self):
        # Phase 0 runs without --mode; the JSON must not claim a resolved
        # mode it was never given (a `"new"` default read as the resolved
        # mode on an arm run) — orient.py's --mode help states null.
        data = orientation_of(self.cwd)
        self.assertIsNone(data["mode"])

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
                {"configWritten", "configPath", "claudeMdWritten", "claudeMdPath", "docsHome", "changed", "dryRun"},
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


class AdoptConfigShadowingTests(unittest.TestCase):
    """adopt.py must never write a second, higher-priority config when one
    is already loaded from the root promise.config.json fallback
    (architecture.md §6's own load order): a fresh `.claude/…` config
    with "map": null would silently shadow a real map underneath it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def test_root_fallback_config_with_a_map_is_never_shadowed(self) -> None:
        root_config_path = Path(self.cwd) / "promise.config.json"
        root_map = {
            "recipe": "docs/testing/adding-a-capability.md",
            "find": "scripts/capability-find",
            "row": "scripts/capability-find --row",
            "lanes": {"data": "tests[]"},
        }
        root_config_path.write_text(
            json.dumps({"docsHome": "docs/designs", "map": root_map}, indent=2), encoding="utf-8"
        )

        result = run(ADOPT, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)

        self.assertFalse(data["configWritten"])
        self.assertFalse((Path(self.cwd) / ".claude" / "promise.config.json").exists())
        self.assertEqual(data["configPath"], str(root_config_path.resolve()))

        orientation = orientation_of(self.cwd)
        self.assertTrue(orientation["config"]["loaded"])
        self.assertEqual(orientation["map"], root_map)
        self.assertTrue(orientation["mapUsable"])
        self.assertTrue(orientation["adopted"])

    def test_claude_md_points_at_the_loaded_root_path_not_dot_claude(self) -> None:
        root_config_path = Path(self.cwd) / "promise.config.json"
        root_config_path.write_text(
            json.dumps({"map": {"recipe": "r", "find": "f", "row": "r", "lanes": {}}}),
            encoding="utf-8",
        )

        run(ADOPT, "--cwd", self.cwd)
        claude_md = (Path(self.cwd) / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("promise.config.json", claude_md)
        self.assertNotIn(".claude/promise.config.json", claude_md)

    def test_primary_path_config_is_unaffected_by_the_fix(self) -> None:
        # No root fallback in play at all: a config loaded from the
        # primary .claude/ path behaves exactly as before.
        claude_dir = Path(self.cwd) / ".claude"
        claude_dir.mkdir(parents=True)
        primary_path = claude_dir / "promise.config.json"
        original_text = '{\n  "docsHome": "docs/rfcs",\n  "map": null\n}\n'
        primary_path.write_text(original_text, encoding="utf-8")

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertFalse(data["configWritten"])
        self.assertEqual(data["configPath"], str(primary_path.resolve()))
        self.assertEqual(primary_path.read_text(encoding="utf-8"), original_text)


class AdoptMalformedMarkersTests(unittest.TestCase):
    """An unmatched or duplicated promise:begin marker must never delete
    content. adopt.py refuses — exit 2, nothing written, the file left
    byte-identical — rather than guessing which lines belong to the
    managed block."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name
        self.claude_md = Path(self.cwd) / "CLAUDE.md"

    def _assert_refused(self, fixture_name: str, expected_line_fragment: str) -> None:
        original = (FIXTURES_DIR / "hardening" / fixture_name).read_bytes()
        self.claude_md.write_bytes(original)

        result = run(ADOPT, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(self.claude_md.read_bytes(), original, "the file must stay byte-identical")
        self.assertIn("promise:begin/end markers", result.stderr)
        self.assertIn(expected_line_fragment, result.stderr)

        data = json.loads(result.stdout)
        self.assertFalse(data["changed"])
        self.assertFalse(data["claudeMdWritten"])
        self.assertFalse(data["configWritten"])
        # nothing else gets written either, in the SAME invocation
        self.assertFalse((Path(self.cwd) / ".claude" / "promise.config.json").exists())

    def test_begin_without_end_is_refused(self) -> None:
        self._assert_refused("markers-begin-no-end.md", "begin at line 5; end at line none")

    def test_end_without_begin_is_refused(self) -> None:
        self._assert_refused("markers-end-no-begin.md", "begin at line none; end at line 7")

    def test_two_begins_is_refused(self) -> None:
        self._assert_refused("markers-two-begins.md", "begin at line 3, 5; end at line 7")

    def test_end_before_begin_is_refused(self) -> None:
        self._assert_refused("markers-end-before-begin.md", "begin at line 7; end at line 3")

    def test_reproduction_begin_no_end_survives_two_runs(self) -> None:
        """The original failure mode: a begin marker with no end, then a
        run, then a second run — which used to pair the orphan begin with
        the END marker THAT FIRST RUN HAD JUST APPENDED, deleting
        everything between them. Both runs now refuse instead."""
        original = (
            "# Project notes\n\nKeep this line.\n\n"
            "<!-- promise:begin (managed by the promise skill; run /promise adopt to refresh it) -->\n"
            "Important hand-written text that must survive.\n"
        )
        self.claude_md.write_text(original, encoding="utf-8")

        first = run(ADOPT, "--cwd", self.cwd)
        self.assertEqual(first.returncode, 2)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), original)

        second = run(ADOPT, "--cwd", self.cwd)
        self.assertEqual(second.returncode, 2)
        after = self.claude_md.read_text(encoding="utf-8")
        self.assertEqual(after, original)
        self.assertIn("Keep this line.", after)
        self.assertIn("Important hand-written text that must survive.", after)

    def test_no_claude_md_flag_bypasses_the_check(self) -> None:
        # A malformed file is only a problem for the file we would touch.
        original = (FIXTURES_DIR / "hardening" / "markers-begin-no-end.md").read_bytes()
        self.claude_md.write_bytes(original)

        result = run(ADOPT, "--cwd", self.cwd, "--no-claude-md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.claude_md.read_bytes(), original)
        data = json.loads(result.stdout)
        self.assertTrue(data["configWritten"])

    def test_dry_run_also_refuses(self) -> None:
        original = (FIXTURES_DIR / "hardening" / "markers-two-begins.md").read_bytes()
        self.claude_md.write_bytes(original)

        result = run(ADOPT, "--cwd", self.cwd, "--dry-run")
        self.assertEqual(result.returncode, 2)
        data = json.loads(result.stdout)
        self.assertFalse(data["changed"])
        self.assertEqual(self.claude_md.read_bytes(), original)


class AdoptByteFidelityTests(unittest.TestCase):
    """Byte fidelity and atomic writes: a UTF-8 BOM and the file's
    dominant line ending survive a rewrite (inside the freshly rendered
    block, not only around it), and every write goes through a temp file
    plus os.replace, leaving nothing stray behind."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name
        self.claude_md = Path(self.cwd) / "CLAUDE.md"

    def test_bom_and_crlf_survive_a_fresh_insert(self) -> None:
        text = "# Project notes\r\n\r\nKeep this line.\r\n"
        self.claude_md.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertTrue(data["claudeMdWritten"])

        after = self.claude_md.read_bytes()
        self.assertTrue(after.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"<!-- promise:begin", after)
        # every "\n" is part of a "\r\n" pair -- the inserted block is CRLF too
        self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
        self.assertIn(b"Keep this line.", after)

    def test_bom_and_crlf_survive_a_replace_in_place(self) -> None:
        before_block = "# Project notes\r\n\r\nKeep this line before.\r\n\r\n"
        stale_block = (
            "<!-- promise:begin (managed by the promise skill; run /promise adopt to refresh it) -->\r\n"
            "stale rendered content from an older template\r\n"
            "<!-- promise:end -->\r\n"
        )
        after_block = "\r\n## Trailer\r\n\r\nKeep this line after.\r\n"
        original = before_block + stale_block + after_block
        self.claude_md.write_bytes(b"\xef\xbb\xbf" + original.encode("utf-8"))

        result = run(ADOPT, "--cwd", self.cwd)
        data = json.loads(result.stdout)
        self.assertTrue(data["claudeMdWritten"])

        after = self.claude_md.read_bytes()
        self.assertTrue(after.startswith(b"\xef\xbb\xbf" + before_block.encode("utf-8")))
        self.assertTrue(after.endswith(after_block.encode("utf-8")))
        self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
        self.assertNotIn(b"stale rendered content from an older template", after)

    def test_content_outside_markers_is_byte_identical_plain_lf(self) -> None:
        before_block = "# Project notes\n\nKeep this line before.\n\n"
        stale_block = (
            "<!-- promise:begin (managed by the promise skill; run /promise adopt to refresh it) -->\n"
            "stale rendered content from an older template\n"
            "<!-- promise:end -->\n"
        )
        after_block = "\n## Trailer\n\nKeep this line after.\n"
        original = before_block + stale_block + after_block
        self.claude_md.write_text(original, encoding="utf-8")

        run(ADOPT, "--cwd", self.cwd)

        after = self.claude_md.read_bytes()
        self.assertTrue(after.startswith(before_block.encode("utf-8")))
        self.assertTrue(after.endswith(after_block.encode("utf-8")))

    def test_no_bom_file_gets_no_bom(self) -> None:
        self.claude_md.write_text("# Project notes\n\nKeep this.\n", encoding="utf-8")
        run(ADOPT, "--cwd", self.cwd)
        after = self.claude_md.read_bytes()
        self.assertFalse(after.startswith(b"\xef\xbb\xbf"))

    def test_no_stray_temp_files_left_behind(self) -> None:
        run(ADOPT, "--cwd", self.cwd)
        stray = [e for e in os.listdir(self.cwd) if e.startswith(".promise-adopt-")]
        self.assertEqual(stray, [])
        claude_dir = Path(self.cwd) / ".claude"
        if claude_dir.is_dir():
            stray_in_claude = [e for e in os.listdir(claude_dir) if e.startswith(".promise-adopt-")]
            self.assertEqual(stray_in_claude, [])


class OrientConfigValidationTests(unittest.TestCase):
    """A malformed config value is a warning naming the key, never a
    crash: the value is treated as absent (falling through to detection
    where detection exists), and the raw config still comes back intact
    under config.raw regardless of what config exposes at top level."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def test_docs_home_wrong_type_warns_and_falls_to_detection(self) -> None:
        docs_dir = Path(self.cwd) / "docs" / "designs"
        docs_dir.mkdir(parents=True)
        write_config(self.cwd, {"docsHome": 42})
        data = orientation_of(self.cwd)
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertEqual(data["docsHomeSource"], "detected")
        self.assertTrue(any("docsHome is not a string" in w for w in data["warnings"]))
        self.assertEqual(data["config"]["raw"]["docsHome"], 42)

    def test_commands_wrong_type_warns_and_falls_to_detection(self) -> None:
        write_config(self.cwd, {"commands": "run the tests please"})
        data = orientation_of(self.cwd)
        self.assertEqual(data["commands"]["source"], "none")
        self.assertIsNone(data["commands"]["typeCheck"])
        self.assertTrue(any("commands is not an object" in w for w in data["warnings"]))

    def test_unknown_commands_key_warns_without_dropping_the_known_ones(self) -> None:
        write_config(self.cwd, {"commands": {"typeCheck": "tsc", "bogus": "x"}})
        data = orientation_of(self.cwd)
        self.assertEqual(data["commands"]["typeCheck"], "tsc")
        self.assertTrue(any("unknown commands key: bogus" in w for w in data["warnings"]))

    def test_map_wrong_type_becomes_null(self) -> None:
        write_config(self.cwd, {"map": "not an object"})
        data = orientation_of(self.cwd)
        self.assertIsNone(data["map"])
        self.assertFalse(data["mapUsable"])
        self.assertTrue(any("map is not an object" in w for w in data["warnings"]))

    def test_map_lanes_wrong_type_warns(self) -> None:
        write_config(
            self.cwd,
            {
                "map": {
                    "recipe": "docs/r.md", "find": "f", "row": "r",
                    "lanes": ["not", "an", "object"],
                }
            },
        )
        data = orientation_of(self.cwd)
        self.assertTrue(any("map.lanes is not an object of strings" in w for w in data["warnings"]))
        self.assertFalse(data["mapUsable"])

    def test_unknown_map_key_warns_but_does_not_block_usability(self) -> None:
        write_config(
            self.cwd,
            {
                "map": {
                    "recipe": "docs/r.md", "find": "f", "row": "r",
                    "lanes": {"data": "tests[]"}, "bogusKey": 1,
                }
            },
        )
        data = orientation_of(self.cwd)
        self.assertTrue(any("unknown map key: bogusKey" in w for w in data["warnings"]))
        self.assertTrue(data["mapUsable"])

    def test_incomplete_map_keeps_the_object_and_flags_unusable(self) -> None:
        write_config(self.cwd, {"map": {"recipe": "docs/r.md", "lanes": {"data": "tests[]"}}})
        data = orientation_of(self.cwd)
        self.assertEqual(data["map"], {"recipe": "docs/r.md", "lanes": {"data": "tests[]"}})
        self.assertFalse(data["mapUsable"])
        self.assertTrue(any("map incomplete: missing find, row" in w for w in data["warnings"]))

    def test_complete_map_is_usable(self) -> None:
        data = orientation_of(str(FIXTURES_DIR / "minirepo"))
        self.assertTrue(data["mapUsable"])

    def test_map_absent_is_not_usable(self) -> None:
        data = orientation_of(self.cwd)
        self.assertIsNone(data["map"])
        self.assertFalse(data["mapUsable"])

    def test_bad_row_id_pattern_warns_even_without_input_flag(self) -> None:
        write_config(
            self.cwd,
            {
                "map": {
                    "recipe": "docs/r.md", "find": "f", "row": "r",
                    "lanes": {"data": "tests[]"}, "rowIdPattern": "[unclosed(",
                }
            },
        )
        data = orientation_of(self.cwd)
        self.assertTrue(any("map.rowIdPattern does not compile" in w for w in data["warnings"]))

    def test_framework_path_missing_file_warns_and_falls_back(self) -> None:
        write_config(self.cwd, {"frameworkPath": "docs/does-not-exist.md"})
        data = orientation_of(self.cwd)
        self.assertEqual(data["frameworkSource"], "bundled")
        self.assertTrue(any("frameworkPath does not exist" in w for w in data["warnings"]))

    def test_absolute_docs_home_warns_and_escapes(self) -> None:
        write_config(self.cwd, {"docsHome": "/etc/passwd"})
        data = orientation_of(self.cwd)
        self.assertIsNone(data["docsHome"])
        self.assertEqual(data["docsHomeSource"], "none")
        self.assertTrue(any("path escapes the project: docsHome" in w for w in data["warnings"]))

    def test_dot_dot_plans_folder_warns_and_escapes(self) -> None:
        write_config(self.cwd, {"plansFolder": "../outside"})
        data = orientation_of(self.cwd)
        self.assertIsNone(data["plansFolder"])
        self.assertTrue(any("path escapes the project: plansFolder" in w for w in data["warnings"]))

    def test_absolute_framework_path_warns_and_falls_back(self) -> None:
        write_config(self.cwd, {"frameworkPath": "/etc/passwd"})
        data = orientation_of(self.cwd)
        self.assertEqual(data["frameworkSource"], "bundled")
        self.assertTrue(any("path escapes the project: frameworkPath" in w for w in data["warnings"]))

    def test_garbage_config_values_never_traceback(self) -> None:
        write_config(
            self.cwd,
            {
                "docsHome": [1, 2, 3],
                "commands": [1, 2],
                "map": 123,
                "plansFolder": {"a": 1},
                "frameworkPath": True,
            },
        )
        result = run(ORIENT, "--cwd", self.cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        data = json.loads(result.stdout)
        self.assertIsNone(data["map"])
        self.assertFalse(data["mapUsable"])
        self.assertIsNone(data["docsHome"])
        self.assertIsNone(data["plansFolder"])
        self.assertEqual(data["frameworkSource"], "bundled")


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
