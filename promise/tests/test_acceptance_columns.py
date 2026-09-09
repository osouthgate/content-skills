"""Acceptance-table columns are read by HEADER NAME, not position.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

A real doc's SS6 header is not guaranteed to be exactly `# | Given | When |
Then | Row`: an extra column (a `Label`) can sit anywhere, and `Row` can
appear in any position, or not at all. `lint_outcome.parse_acceptance_rows`
maps every column by its header text (case-insensitive, trimmed) through
`acceptance_column_map`, and `find_acceptance_tables`/`check_acceptance_table`
(the ACCEPTANCE_TABLE rule) use the same map to decide whether a table
qualifies at all — Given, When and Then must each appear by name; Row is
optional and, absent, every row's `row` reads as None rather than as
whatever cell happens to sit at the old fixed position.

Fixtures live under fixtures/acceptance-columns/, each conforming.md with
one change to SS6's table shape (and, for the `_agreed` variant, the status
and rule tags a bridged doc needs). test_lint_hardening.py and test_scripts.py
cover the pre-existing fixtures (a header that already names Given/When/Then
in the template's own order) and must keep passing unchanged — this module
covers the new, name-based cases only.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "acceptance-columns"
CONFORMING = TESTS_DIR / "fixtures" / "conforming.md"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

LINT = SCRIPTS_DIR / "lint_outcome.py"
ROWS = SCRIPTS_DIR / "outcome_rows.py"
BRIDGE = SCRIPTS_DIR / "bridge_validate.py"
TEMPLATE = SCRIPTS_DIR.parent / "templates" / "outcome-doc.md"
FAKE_ROW = TESTS_DIR / "fixtures" / "bridge" / "fake_row.py"

LABEL_NO_ROW = FIXTURES_DIR / "label_column_no_row.md"
LABEL_NO_ROW_AGREED = FIXTURES_DIR / "label_column_no_row_agreed.md"
ROW_SECOND = FIXTURES_DIR / "row_second_column.md"
HEADER_MISSING_THEN = FIXTURES_DIR / "header_missing_then.md"


def run_json(script: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(script), *args], capture_output=True, text=True
    )
    return json.loads(result.stdout)


def write_config(project_dir: Path, config: dict) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def fixture_command(path: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(path))}"


class FixturesExistTests(unittest.TestCase):
    def test_every_fixture_exists(self) -> None:
        for path in (LABEL_NO_ROW, LABEL_NO_ROW_AGREED, ROW_SECOND, HEADER_MISSING_THEN):
            self.assertTrue(path.is_file(), f"missing fixture: {path}")

    def test_each_new_fixture_is_conforming_plus_one_table_change(self) -> None:
        conforming_lines = CONFORMING.read_text(encoding="utf-8").splitlines()
        for path in (LABEL_NO_ROW, ROW_SECOND, HEADER_MISSING_THEN):
            lines = path.read_text(encoding="utf-8").splitlines()
            # Same line count: only the SS6 table's own lines were rewritten
            # (a straight header+row replacement), nothing inserted or removed.
            self.assertEqual(len(lines), len(conforming_lines), path.name)


class LabelColumnNoRowTests(unittest.TestCase):
    """(1) An extra `Label` column, second, and no `Row` column at all."""

    def test_lints_clean(self) -> None:
        data = run_json(LINT, str(LABEL_NO_ROW), "--json")
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_outcome_rows_reads_the_real_given_when_then(self) -> None:
        data = run_json(ROWS, str(LABEL_NO_ROW), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id["AT-1"]["given"], "Ana is in a channel")
        self.assertEqual(by_id["AT-1"]["when"], "she mutes it")
        self.assertEqual(by_id["AT-1"]["then"], "she gets no push or badge from it")
        self.assertEqual(by_id["AT-3"]["then"], "Ben is still notified normally")
        # The Label column's content must never leak into a named field.
        for r in data["rows"]:
            self.assertNotEqual(r["given"], "routine")
            self.assertNotEqual(r["when"], "routine")
            self.assertNotEqual(r["then"], "routine")

    def test_outcome_rows_row_is_null_with_no_row_column(self) -> None:
        data = run_json(ROWS, str(LABEL_NO_ROW), "--json")
        for r in data["rows"]:
            self.assertIsNone(r["row"], r)

    def test_bridge_validate_reports_row_missing_not_row_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(
                project,
                {
                    "map": {
                        "recipe": "docs/how-to/adding-a-row.md",
                        "find": fixture_command(FAKE_ROW),
                        "row": fixture_command(FAKE_ROW),
                        "rowIdPattern": r"^R\d+$",
                    }
                },
            )
            data = run_json(
                BRIDGE, str(LABEL_NO_ROW_AGREED), "--cwd", str(project), "--json"
            )
            rules = [f["rule"] for f in data["findings"]]
            self.assertEqual(rules.count("ROW_MISSING"), 3, rules)
            self.assertNotIn("ROW_ID_FORMAT", rules, rules)
            self.assertNotIn("ROW_NOT_FOUND", rules, rules)
            for row in data["rows"]:
                self.assertIsNone(row["row"])


class RowSecondColumnTests(unittest.TestCase):
    """(2) `Row` as the SECOND column."""

    def test_lints_clean(self) -> None:
        data = run_json(LINT, str(ROW_SECOND), "--json")
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_outcome_rows_reads_row_from_its_named_position(self) -> None:
        data = run_json(ROWS, str(ROW_SECOND), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertEqual(by_id["AT-1"]["row"], "R1")
        self.assertEqual(by_id["AT-2"]["row"], "R1")
        self.assertEqual(by_id["AT-3"]["row"], "R2")
        # Given/When/Then still read correctly despite Row sitting before them.
        self.assertEqual(by_id["AT-1"]["given"], "Ana is in a channel")
        self.assertEqual(by_id["AT-1"]["when"], "she mutes it")
        self.assertEqual(by_id["AT-1"]["then"], "she gets no push or badge from it")


class HeaderMissingThenTests(unittest.TestCase):
    """(3) A header that lacks `Then` (an unrelated `Notes` column instead)."""

    def test_acceptance_table_fires_alone(self) -> None:
        data = run_json(LINT, str(HEADER_MISSING_THEN), "--json")
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["ACCEPTANCE_TABLE"])
        finding = next(f for f in data["findings"] if f["rule"] == "ACCEPTANCE_TABLE")
        self.assertIn("no acceptance table", finding["message"])

    def test_row_count_and_ids_are_unaffected(self) -> None:
        # The header not qualifying by name must not also erase every row
        # for SCENARIOS_COUNT/TAGS_RESOLVE — only ACCEPTANCE_TABLE above
        # fired, which it could not have if those two had also tripped.
        data = run_json(ROWS, str(HEADER_MISSING_THEN), "--json")
        self.assertEqual(len(data["rows"]), 3)


class RegressionGuardTests(unittest.TestCase):
    """conforming.md, the pre-existing hardening fixtures, the template and
    the bridge fixtures must behave exactly as they did before this fix."""

    def test_conforming_still_lints_clean(self) -> None:
        data = run_json(LINT, str(CONFORMING), "--json")
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_conforming_rows_unchanged(self) -> None:
        data = run_json(ROWS, str(CONFORMING), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertEqual(by_id["AT-1"]["given"], "Ana is in a channel")
        self.assertEqual(by_id["AT-1"]["then"], "she gets no push or badge from it")
        self.assertIsNone(by_id["AT-1"]["row"])

    def test_template_still_passes_the_lint(self) -> None:
        result = subprocess.run(
            [sys.executable, str(LINT), str(TEMPLATE), "--template"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_template_row_column_still_reads_by_name(self) -> None:
        # The template's own SS6 header is `# | Given | When | Then | Row`
        # (architecture.md's canonical shape) -- confirms the Row-by-name
        # path still recognises the template's own column, empty as it is.
        data = run_json(ROWS, str(TEMPLATE), "--json")
        self.assertGreaterEqual(len(data["rows"]), 1)
        for r in data["rows"]:
            self.assertIsNone(r["row"])

    def test_pre_existing_lint_hardening_fixtures_pass(self) -> None:
        hardening_dir = TESTS_DIR / "fixtures" / "lint-hardening"
        expected = {
            "acceptance_table_missing.md": "ACCEPTANCE_TABLE",
            "acceptance_table_no_rows.md": "ACCEPTANCE_TABLE",
            "acceptance_table_empty_cell.md": "ACCEPTANCE_TABLE",
            "acceptance_table_wrong_cell_count.md": "ACCEPTANCE_TABLE",
            "acceptance_table_bad_header_width.md": "ACCEPTANCE_TABLE",
        }
        for filename, rule in expected.items():
            with self.subTest(fixture=filename):
                data = run_json(LINT, str(hardening_dir / filename), "--json")
                error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
                self.assertEqual(error_rules, [rule], f"{filename}: got {error_rules}")

    def test_bridge_agreed_bridged_fixture_still_behaves(self) -> None:
        # promise/tests/fixtures/bridge/agreed_bridged.md's own suite
        # (test_bridge_validate.py) already covers this in full; this is a
        # narrow smoke check that outcome_rows.py's extraction of its
        # standard `# | Given | When | Then | Row` header is unaffected.
        bridge_fixture = TESTS_DIR / "fixtures" / "bridge" / "agreed_bridged.md"
        data = run_json(ROWS, str(bridge_fixture), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertEqual(by_id["AT-1"]["row"], "R1")
        self.assertEqual(by_id["AT-3"]["row"], "R2")
        self.assertEqual(by_id["AT-1"]["then"], "she gets no push or badge from it")


if __name__ == "__main__":
    unittest.main()
