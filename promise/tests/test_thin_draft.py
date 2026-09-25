"""Tests for the thin draft: a `draft` doc that holds the human half only.

A thin draft carries `Depth: thin` in its header. The lint accepts it with
no §6 table, no §4-§7 Why lines, no §3 example and, as a warning, no rule;
it rejects `Depth: thin` on any status past `draft` (THIN_DRAFT), so a thin
doc cannot be agreed. `render_outcome.py --thin` writes the shape.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"
RENDER = SCRIPTS_DIR / "render_outcome.py"
THIN = FIXTURES_DIR / "thin_conforming.md"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def lint_text(text: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        result = run(LINT, str(path), "--json")
        data = json.loads(result.stdout)
        data["returncode"] = result.returncode
        return data


class ThinDraftLint(unittest.TestCase):
    def test_filled_thin_draft_lints_clean(self):
        data = lint_text(THIN.read_text(encoding="utf-8"))
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["returncode"], 0)

    def test_thin_on_agreed_is_an_error(self):
        text = THIN.read_text(encoding="utf-8").replace("Status: draft", "Status: agreed", 1)
        data = lint_text(text)
        thin = [f for f in data["findings"] if f["rule"] == "THIN_DRAFT"]
        self.assertEqual(len(thin), 1, data["findings"])
        self.assertEqual(thin[0]["severity"], "error")
        self.assertIn("agreed", thin[0]["message"])
        # Past draft the doc is held to the full shape again.
        rules = {f["rule"] for f in data["findings"]}
        self.assertIn("ACCEPTANCE_TABLE", rules)
        self.assertIn("WHY_LINE", rules)

    def test_depth_other_than_thin_is_an_error(self):
        data = lint_text((FIXTURES_DIR / "thin_draft.md").read_text(encoding="utf-8"))
        self.assertEqual([f["rule"] for f in data["findings"]], ["THIN_DRAFT"])

    def test_empty_rules_is_a_warning_on_a_thin_draft(self):
        text = THIN.read_text(encoding="utf-8")
        rule = "- A muted channel never sends a push or a badge count until it is unmuted.  → UNTESTED\n"
        self.assertIn(rule, text)
        data = lint_text(text.replace(rule, "", 1))
        self.assertEqual(
            [(f["rule"], f["severity"]) for f in data["findings"]], [("RULES_PRESENT", "warn")]
        )
        self.assertEqual(data["returncode"], 0)

    def test_empty_rules_stays_an_error_on_a_full_draft(self):
        text = THIN.read_text(encoding="utf-8").replace("Depth: thin\n", "", 1)
        rule = "- A muted channel never sends a push or a badge count until it is unmuted.  → UNTESTED\n"
        data = lint_text(text.replace(rule, "", 1))
        present = [f for f in data["findings"] if f["rule"] == "RULES_PRESENT"]
        self.assertEqual([f["severity"] for f in present], ["error"])

    def test_a_table_on_a_thin_draft_is_still_checked(self):
        text = THIN.read_text(encoding="utf-8").replace(
            "## 6. Acceptance\n*(agent drafts, human confirms)*\n",
            "## 6. Acceptance\n*(agent drafts, human confirms)*\n\n"
            "| # | Given | When | Then | Altitude | Row |\n"
            "|---|-------|------|------|----------|-----|\n"
            "| AT-1 | a | b |  | data |  |\n",
            1,
        )
        rules = {f["rule"] for f in lint_text(text)["findings"]}
        self.assertIn("ACCEPTANCE_TABLE", rules)

    def test_scenarios_claim_is_still_checked(self):
        text = THIN.read_text(encoding="utf-8").replace("0 worked examples", "1 worked example", 1)
        rules = [f["rule"] for f in lint_text(text)["findings"]]
        self.assertEqual(rules, ["SCENARIOS_COUNT"])


class ThinRender(unittest.TestCase):
    def render(self, *extra: str) -> str:
        result = run(
            RENDER, "--title", "Channel muting", "--owner", "Priya", "--date", "2026-01-01",
            "--docs-home", "unused", "--dry-run", *extra,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_thin_render_adds_depth_and_cuts_the_agent_half(self):
        text = self.render("--thin")
        self.assertIn("\nSupersedes: —\nDepth: thin\n", text)
        self.assertIn("**Scenarios:** 0 acceptance rows (§6), 0 worked examples (§3).", text)
        self.assertEqual(text.count("→ UNTESTED"), 1)
        self.assertNotIn("→ AT-", text)
        self.assertNotIn("| AT-1", text)
        self.assertNotIn("Why — what breaks without it:", text)
        self.assertEqual(text.count("this is a thin draft"), 5)

    def test_raw_thin_render_reports_only_placeholders(self):
        rules = {f["rule"] for f in lint_text(self.render("--thin"))["findings"]}
        self.assertEqual(rules, {"PLACEHOLDER"})

    def test_filled_fixture_matches_the_thin_render_shape(self):
        # The fixture is the thin render with its slots filled; every line
        # outside §0, the agent notes and §9 is the render's line.
        rendered = self.render("--thin").splitlines()
        fixture = THIN.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rendered), len(fixture))
        differing = [i for i, (a, b) in enumerate(zip(rendered, fixture)) if a != b]
        self.assertEqual(len(differing), 5, differing)

    def test_full_render_is_unchanged_without_the_flag(self):
        text = self.render()
        self.assertNotIn("Depth:", text)
        self.assertIn("| AT-1", text)


if __name__ == "__main__":
    unittest.main()
