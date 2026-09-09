"""Hardening tests for lint_outcome.py: the checks that catch a materially
empty or malformed outcome doc that the base rule set let through.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Mirrors test_scripts.py's own conventions: scripts and fixtures are located
relative to this file rather than the current working directory, and
lint_outcome.py is exercised as a real subprocess (argv, stdout, stderr,
exit code) — never imported and called in-process. Fixtures live under
fixtures/lint-hardening/, each the conforming doc with exactly one change
(occasionally a second, mechanically-forced change — a tag or a count —
where leaving it out would trip a pre-existing, unrelated rule instead of
the one under test; see the ACCEPTANCE_TABLE "missing"/"no rows" fixtures).
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

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
HARDENING_DIR = FIXTURES_DIR / "lint-hardening"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

LINT = SCRIPTS_DIR / "lint_outcome.py"
TEMPLATE = SCRIPTS_DIR.parent / "templates" / "outcome-doc.md"

# Every new-rule-hardening fixture, and the single error rule it must trip
# alone. Each is the conforming doc with exactly one change (see module
# docstring for the two exceptions).
NEW_FIXTURES = {
    "tldr_fields_empty_outcome.md": "TLDR_FIELDS",
    "tldr_fields_empty_how_we_know.md": "TLDR_FIELDS",
    "rules_format_stray_line.md": "RULES_FORMAT",
    "rules_format_bullet_no_text.md": "RULES_FORMAT",
    "acceptance_table_missing.md": "ACCEPTANCE_TABLE",
    "acceptance_table_no_rows.md": "ACCEPTANCE_TABLE",
    "acceptance_table_empty_cell.md": "ACCEPTANCE_TABLE",
    "acceptance_table_wrong_cell_count.md": "ACCEPTANCE_TABLE",
    "acceptance_table_bad_header_width.md": "ACCEPTANCE_TABLE",
    "headings_bare_duplicate_masked.md": "HEADINGS_BARE",
    "placeholder_angle_in_tldr.md": "PLACEHOLDER",
    "placeholder_angle_in_header_owner.md": "PLACEHOLDER",
    "placeholder_yyyy_mm_dd_in_header.md": "PLACEHOLDER",
    "placeholder_angle_in_acceptance_cell.md": "PLACEHOLDER",
    "header_owner_empty_owner.md": "HEADER_OWNER",
    "header_owner_empty_last_decision.md": "HEADER_OWNER",
    "header_status_superseded_no_target.md": "HEADER_STATUS",
}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LINT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def lint_json(*args: str) -> dict:
    result = run(*args)
    return json.loads(result.stdout)


class NewFixturesExistTests(unittest.TestCase):
    def test_every_new_fixture_exists(self) -> None:
        for filename in NEW_FIXTURES:
            self.assertTrue((HARDENING_DIR / filename).is_file(), f"missing fixture: {filename}")

    def test_not_utf8_fixture_exists_and_is_genuinely_invalid(self) -> None:
        path = HARDENING_DIR / "not_utf8.md"
        self.assertTrue(path.is_file())
        with self.assertRaises(UnicodeDecodeError):
            path.read_text(encoding="utf-8-sig")


class EachHardeningFixtureTripsOnlyItsRule(unittest.TestCase):
    """Same contract as test_scripts.py's LintErrorRuleFixtureTests, applied
    to the new-rule fixtures: the named rule fires, as an error, and no
    OTHER error-severity rule fires alongside it."""

    def test_each_fixture_trips_only_its_rule(self) -> None:
        for filename, rule in NEW_FIXTURES.items():
            with self.subTest(fixture=filename, rule=rule):
                path = HARDENING_DIR / filename
                result = run(str(path), "--json")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                data = json.loads(result.stdout)
                error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
                self.assertEqual(
                    error_rules,
                    [rule],
                    f"{filename}: expected only {rule} to fire as an error, got {error_rules}",
                )

    def test_human_output_format_unchanged_for_a_new_rule(self) -> None:
        result = run(str(HARDENING_DIR / "header_status_superseded_no_target.md"))
        self.assertEqual(result.returncode, 1)
        line = result.stdout.strip().splitlines()[0]
        self.assertIn("HEADER_STATUS", line)
        self.assertTrue(line.startswith(str(HARDENING_DIR / "header_status_superseded_no_target.md")))


class TldrFieldsEmptyValueTests(unittest.TestCase):
    def test_empty_outcome_value_is_reported_on_its_own_line(self) -> None:
        data = lint_json(str(HARDENING_DIR / "tldr_fields_empty_outcome.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "TLDR_FIELDS"]
        self.assertEqual(len(findings), 1)
        self.assertIn("Outcome", findings[0]["message"])
        self.assertEqual(findings[0]["line"], 16)

    def test_empty_how_we_know_value_is_reported(self) -> None:
        data = lint_json(str(HARDENING_DIR / "tldr_fields_empty_how_we_know.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "TLDR_FIELDS"]
        self.assertEqual(len(findings), 1)
        self.assertIn("How we'll know", findings[0]["message"])

    def test_conforming_fixture_has_no_tldr_fields_finding(self) -> None:
        data = lint_json(str(FIXTURES_DIR / "conforming.md"), "--json")
        self.assertFalse(any(f["rule"] == "TLDR_FIELDS" for f in data["findings"]))


class RulesFormatHardeningTests(unittest.TestCase):
    def test_stray_line_message_matches_the_spec_wording(self) -> None:
        data = lint_json(str(HARDENING_DIR / "rules_format_stray_line.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "RULES_FORMAT"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["message"], "text in the rules block is not a rule bullet")

    def test_bullet_with_no_text_before_tag_is_reported(self) -> None:
        data = lint_json(str(HARDENING_DIR / "rules_format_bullet_no_text.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "RULES_FORMAT"]
        self.assertEqual(len(findings), 1)
        self.assertIn("no text", findings[0]["message"])

    def test_numbered_rule_fixture_still_trips_only_rules_format(self) -> None:
        # Regression guard on the pre-existing fixture: the indentation fix
        # to parse_rules_block must not change how a numbered rule is judged.
        data = lint_json(str(FIXTURES_DIR / "rules_format.md"), "--json")
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["RULES_FORMAT"])

    def test_conforming_fixture_has_no_rules_format_finding(self) -> None:
        data = lint_json(str(FIXTURES_DIR / "conforming.md"), "--json")
        self.assertFalse(any(f["rule"] == "RULES_FORMAT" for f in data["findings"]))


class AcceptanceTableTests(unittest.TestCase):
    def test_missing_table_names_the_shape_it_needs(self) -> None:
        data = lint_json(str(HARDENING_DIR / "acceptance_table_missing.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("no acceptance table", findings[0]["message"])

    def test_header_at_wrong_width_also_counts_as_no_table(self) -> None:
        data = lint_json(str(HARDENING_DIR / "acceptance_table_bad_header_width.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("no acceptance table", findings[0]["message"])

    def test_no_data_rows_is_reported(self) -> None:
        data = lint_json(str(HARDENING_DIR / "acceptance_table_no_rows.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("no data rows", findings[0]["message"])

    def test_empty_cell_names_the_cell(self) -> None:
        data = lint_json(str(HARDENING_DIR / "acceptance_table_empty_cell.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("Then", findings[0]["message"])
        self.assertIn("empty", findings[0]["message"])

    def test_wrong_cell_count_names_the_counts(self) -> None:
        data = lint_json(str(HARDENING_DIR / "acceptance_table_wrong_cell_count.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("3 cells", findings[0]["message"])
        self.assertIn("expected 4", findings[0]["message"])

    def test_conforming_fixture_has_no_acceptance_table_finding(self) -> None:
        data = lint_json(str(FIXTURES_DIR / "conforming.md"), "--json")
        self.assertFalse(any(f["rule"] == "ACCEPTANCE_TABLE" for f in data["findings"]))

    def test_second_non_acceptance_table_in_s6_still_ignored(self) -> None:
        # architecture.md's own contract: a second, non-acceptance table in
        # SS6 (fixtures/second_table_in_s6.md) is not subject to row rules.
        # ACCEPTANCE_TABLE must honour it exactly like the older SS6 rules.
        result = run(str(FIXTURES_DIR / "second_table_in_s6.md"), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["findings"], [])


class HeadingsBareDuplicateTests(unittest.TestCase):
    def test_malformed_duplicate_fires_even_with_a_valid_heading_present(self) -> None:
        data = lint_json(str(HARDENING_DIR / "headings_bare_duplicate_masked.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "HEADINGS_BARE"]
        self.assertEqual(len(findings), 1)
        self.assertIn("## 6. Acceptance (duplicate)", findings[0]["message"])

    def test_existing_headings_bare_fixture_unaffected(self) -> None:
        # Regression guard: the single-malformed-heading case (no duplicate
        # good heading involved) must report exactly as before.
        result = run(str(FIXTURES_DIR / "headings_bare.md"), "--json")
        data = json.loads(result.stdout)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["HEADINGS_BARE"])
        self.assertEqual(len(data["findings"]), 1)


class PlaceholderExtensionTests(unittest.TestCase):
    def test_angle_bracket_in_tldr_block(self) -> None:
        data = lint_json(str(HARDENING_DIR / "placeholder_angle_in_tldr.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "PLACEHOLDER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("<needs input>", findings[0]["message"])
        self.assertIn("SS0", findings[0]["message"])

    def test_angle_bracket_in_header_owner_value(self) -> None:
        data = lint_json(str(HARDENING_DIR / "placeholder_angle_in_header_owner.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "PLACEHOLDER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("<Priya>", findings[0]["message"])
        self.assertIn("Owner:", findings[0]["message"])

    def test_literal_yyyy_mm_dd_in_header_last_decision_value(self) -> None:
        data = lint_json(str(HARDENING_DIR / "placeholder_yyyy_mm_dd_in_header.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "PLACEHOLDER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("YYYY-MM-DD", findings[0]["message"])
        self.assertIn("Last decision:", findings[0]["message"])

    def test_angle_bracket_in_acceptance_cell(self) -> None:
        data = lint_json(str(HARDENING_DIR / "placeholder_angle_in_acceptance_cell.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "PLACEHOLDER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("<verify>", findings[0]["message"])
        self.assertIn("SS6", findings[0]["message"])

    def test_original_term_based_placeholder_fixture_unaffected(self) -> None:
        # Regression guard: TBD/TODO-style term matching (unrelated to the
        # angle-bracket extension) must still fire exactly as before.
        result = run(str(FIXTURES_DIR / "placeholder.md"), "--json")
        data = json.loads(result.stdout)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["PLACEHOLDER"])

    def test_conforming_fixture_has_no_placeholder_finding(self) -> None:
        data = lint_json(str(FIXTURES_DIR / "conforming.md"), "--json")
        self.assertFalse(any(f["rule"] == "PLACEHOLDER" for f in data["findings"]))


class HeaderOwnerEmptyValueTests(unittest.TestCase):
    def test_missing_owner_field_still_reports_missing_not_empty(self) -> None:
        # Regression guard: the pre-existing "field absent entirely" fixture
        # must keep its original message, distinct from the new "present
        # but empty" case.
        data = lint_json(str(FIXTURES_DIR / "header_owner.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "HEADER_OWNER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("missing", findings[0]["message"])

    def test_empty_owner_value_reports_empty_not_missing(self) -> None:
        data = lint_json(str(HARDENING_DIR / "header_owner_empty_owner.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "HEADER_OWNER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("empty", findings[0]["message"])
        self.assertIn("Owner:", findings[0]["message"])

    def test_empty_last_decision_value_reports_empty(self) -> None:
        data = lint_json(str(HARDENING_DIR / "header_owner_empty_last_decision.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "HEADER_OWNER"]
        self.assertEqual(len(findings), 1)
        self.assertIn("empty", findings[0]["message"])
        self.assertIn("Last decision:", findings[0]["message"])


class HeaderStatusSupersededTests(unittest.TestCase):
    def test_superseded_by_with_no_target_is_an_error(self) -> None:
        data = lint_json(str(HARDENING_DIR / "header_status_superseded_no_target.md"), "--json")
        findings = [f for f in data["findings"] if f["rule"] == "HEADER_STATUS"]
        self.assertEqual(len(findings), 1)
        self.assertIn("superseded-by", findings[0]["message"])

    def test_conforming_fixture_status_draft_has_no_header_status_finding(self) -> None:
        data = lint_json(str(FIXTURES_DIR / "conforming.md"), "--json")
        self.assertFalse(any(f["rule"] == "HEADER_STATUS" for f in data["findings"]))


class TemplateFlagTests(unittest.TestCase):
    def test_template_with_flag_exits_zero(self) -> None:
        result = run("--template", str(TEMPLATE))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_template_without_flag_exits_one_with_only_placeholder_findings(self) -> None:
        data = lint_json(str(TEMPLATE), "--json")
        self.assertGreaterEqual(len(data["findings"]), 1)
        rules = sorted({f["rule"] for f in data["findings"]})
        self.assertEqual(rules, ["PLACEHOLDER"])
        severities = {f["severity"] for f in data["findings"]}
        self.assertEqual(severities, {"error"})

    def test_template_flag_does_not_suppress_other_rules(self) -> None:
        # --template must exempt only the placeholder shapes, not the rest
        # of the rule set: an unrelated, pre-existing error fixture must
        # still fire its own rule when linted with --template.
        result = run("--template", str(FIXTURES_DIR / "contents_line.md"), "--json")
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["CONTENTS_LINE"])

    def test_help_mentions_template_flag(self) -> None:
        result = run("-h")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--template", result.stdout)


class UnreadableTests(unittest.TestCase):
    def test_invalid_utf8_file_reports_one_unreadable_finding_no_traceback(self) -> None:
        path = HARDENING_DIR / "not_utf8.md"
        result = run(str(path), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "", "must not raise/traceback on unreadable content")
        data = json.loads(result.stdout)
        self.assertEqual(len(data["findings"]), 1)
        f = data["findings"][0]
        self.assertEqual(f["rule"], "UNREADABLE")
        self.assertEqual(f["severity"], "error")
        self.assertIsNone(f["line"])
        self.assertEqual(data["stats"], {"errors": 1, "warnings": 0, "total": 1})

    def test_invalid_utf8_file_human_output_has_no_traceback(self) -> None:
        path = HARDENING_DIR / "not_utf8.md"
        result = run(str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        self.assertIn("UNREADABLE", result.stdout)
        self.assertNotIn("Traceback", result.stdout)

    def test_directory_scan_surfaces_an_unreadable_file_alongside_a_good_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "broken.md").write_bytes(
                (HARDENING_DIR / "not_utf8.md").read_bytes()
            )
            (tmp_path / "good.md").write_text(
                (FIXTURES_DIR / "conforming.md").read_text(encoding="utf-8"), encoding="utf-8"
            )
            result = run(str(tmp_path), "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            data = json.loads(result.stdout)
            self.assertEqual(len(data), 2)
            by_path = {os.path.basename(r["path"]): r for r in data}
            self.assertEqual([f["rule"] for f in by_path["broken.md"]["findings"]], ["UNREADABLE"])
            self.assertEqual(by_path["good.md"]["findings"], [])

    @unittest.skipIf(os.name != "posix", "permission bits are POSIX-specific")
    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores file permissions")
    def test_permission_denied_file_reports_unreadable_not_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "no-read.md"
            path.write_text("## 0. TLDR\n", encoding="utf-8")
            path.chmod(0)
            try:
                result = run(str(path), "--json")
            finally:
                # Restore write access before the TemporaryDirectory context
                # tries to remove the directory on the way out.
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            data = json.loads(result.stdout)
            self.assertEqual([f["rule"] for f in data["findings"]], ["UNREADABLE"])

    def test_empty_directory_prints_nothing_and_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(tmp)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_empty_directory_json_is_an_empty_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(tmp, "--json")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), [])


if __name__ == "__main__":
    unittest.main()
