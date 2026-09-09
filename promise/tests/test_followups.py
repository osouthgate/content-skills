"""Tests for three follow-up features on top of the promise skill's scripts:

  * orient.py --input          -- a suggestedMode/signals router hint (architecture.md SS4)
  * outcome_rows.py --write-counts -- corrects a doc's Scenarios: line in place
  * outcome_rows.py --search       -- ranks SS6 rows and SS0 rules by token overlap

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Mirrors test_scripts.py's own conventions: scripts and fixtures are located
relative to this file rather than the current working directory, and every
script is exercised as a real subprocess (argv, stdout, stderr, exit code).
A scenario that needs its own project (particular docs, a particular config)
is built in a temporary directory rather than checked in, so each rule's
precondition is exact and visible in the test itself; the --search fixtures,
which need realistic SS6/SS0 prose to score against, are checked in under
fixtures/followups/search/.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
FOLLOWUPS_DIR = FIXTURES_DIR / "followups"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

ORIENT = SCRIPTS_DIR / "orient.py"
ROWS = SCRIPTS_DIR / "outcome_rows.py"


def run(script: Path, *args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def orient_with_input(cwd: str, input_text: Optional[str]) -> Dict[str, Any]:
    args = ["--cwd", cwd]
    if input_text is not None:
        args += ["--input", input_text]
    result = run(ORIENT, *args)
    return json.loads(result.stdout)


def write_doc(dir_path: Path, filename: str, title: str, status: str) -> Path:
    """A doc with just enough shape for orient.py's existingDocs scan: a SS0
    TLDR heading (so it is picked up at all), an H1 title and a Status:
    line. Nothing here calls lint_outcome.py, so the doc need not carry
    the framework's full eleven sections."""
    doc = (
        f"# {title}\n"
        "\n"
        f"Status: {status}\n"
        "Owner: Priya        Last decision: 2026-01-01\n"
        "\n"
        "## 0. TLDR\n"
        "**Outcome:** placeholder.\n"
        "**Rules:**\n"
        "- placeholder rule.  → AT-1\n"
        "**How we'll know:** placeholder.\n"
        "**Scenarios:** 1 acceptance rows (§6), 0 worked examples (§3).\n"
        "\n"
        "## 6. Acceptance\n"
        "\n"
        "| # | Given | When | Then |\n"
        "|---|-------|------|------|\n"
        "| AT-1 | a | b | c |\n"
    )
    path = dir_path / filename
    path.write_text(doc, encoding="utf-8")
    return path


def make_project(
    tmp_dir: str,
    docs: List[Dict[str, str]],
    row_id_pattern: Optional[str] = None,
) -> None:
    """A temp project: docs/designs/<file> per `docs` ({"filename", "title",
    "status"}), plus a .claude/promise.config.json naming docsHome and,
    when given, a map.rowIdPattern (architecture.md SS6/SS4 rule 7)."""
    docs_home = Path(tmp_dir) / "docs" / "designs"
    docs_home.mkdir(parents=True, exist_ok=True)
    for d in docs:
        write_doc(docs_home, d["filename"], d["title"], d["status"])
    config: Dict[str, Any] = {"docsHome": "docs/designs"}
    if row_id_pattern is not None:
        config["map"] = {"rowIdPattern": row_id_pattern}
    config_dir = Path(tmp_dir) / ".claude"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "promise.config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# FEATURE 1: orient.py --input
# ---------------------------------------------------------------------------


class SuggestModeAbsentFlagTests(unittest.TestCase):
    def test_flag_absent_gives_null_and_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, None)
        self.assertIsNone(data["suggestedMode"])
        self.assertEqual(data["signals"], [])

    def test_both_keys_present_regardless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, None)
        self.assertIn("suggestedMode", data)
        self.assertIn("signals", data)


class SuggestModeRuleTests(unittest.TestCase):
    """One test per architecture.md SS4 rule (FEATURE 1), rules 1-10 in order."""

    def test_rule1_first_word_is_a_mode_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "revise the widget doc please")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertEqual(data["signals"], ["first word is a mode name"])

    def test_rule2_doc_match_plus_critique_verb_is_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "is the foo widget doc any good? please review it")
        self.assertEqual(data["suggestedMode"], "review")
        self.assertTrue(any("Foo widget" in s and "critique verb" in s for s in data["signals"]))

    def test_rule3_two_distinct_doc_matches_is_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(
                tmp,
                [
                    {"filename": "foo.md", "title": "Foo widget", "status": "draft"},
                    {"filename": "bar.md", "title": "Bar widget", "status": "draft"},
                ],
            )
            data = orient_with_input(tmp, "foo widget and bar widget overlap, which one survives?")
        self.assertEqual(data["suggestedMode"], "merge")
        self.assertTrue(any("2 distinct existing docs" in s for s in data["signals"]))

    def test_rule4_one_agreed_match_plus_arm_phrase_is_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "foo widget is agreed, let's kick off the build")
        self.assertEqual(data["suggestedMode"], "arm")
        self.assertTrue(any("agreed" in s and "arm phrase" in s for s in data["signals"]))

    def test_rule5_one_match_otherwise_is_revise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "update the foo widget doc, tighten section 5")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertTrue(any("Foo widget" in s for s in data["signals"]))

    def test_rule6_pr_number_is_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "we already shipped this in PR #42")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_rule7_row_id_pattern_match_is_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [], row_id_pattern=r"^C\d+[a-z]?$")
            data = orient_with_input(tmp, "add this as a scenario to C207a")
        self.assertEqual(data["suggestedMode"], "intake")
        self.assertTrue(any("C207a" in s and "rowIdPattern" in s for s in data["signals"]))

    def test_rule7_bad_row_id_pattern_warns_and_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [], row_id_pattern="[unclosed(")
            result = run(ORIENT, "--cwd", tmp, "--input", "add this as a scenario to C207a")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        # rule 7 is skipped, not crashed past. The phrase "add this as a scenario" is one of
        # the dispatch table's intake phrasings, so the phrase rule still lands on intake —
        # by wording, not by the row id the broken pattern could not check.
        self.assertEqual(data["suggestedMode"], "intake")
        self.assertFalse(any("rowIdPattern" in s for s in data["signals"]), data["signals"])
        self.assertTrue(
            any("rowIdPattern" in w and "skipping rule 7" in w for w in data["warnings"]),
            data["warnings"],
        )

    def test_rule8_three_list_items_is_intake(self) -> None:
        input_text = "users said:\n- too slow\n- confusing\n- crashes often"
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, input_text)
        self.assertEqual(data["suggestedMode"], "intake")
        self.assertTrue(any("list items" in s for s in data["signals"]))

    def test_rule8_feedback_word_is_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "here is some user feedback from the call")
        self.assertEqual(data["suggestedMode"], "intake")
        self.assertTrue(any("feedback" in s for s in data["signals"]))

    def test_rule9_install_near_promise_is_adopt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "please install promise for this repo")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_rule9_claude_md_is_adopt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "add a promise section to CLAUDE.md")
        self.assertEqual(data["suggestedMode"], "adopt")
        self.assertTrue(any("CLAUDE.md" in s for s in data["signals"]))

    def test_rule10_default_is_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "let's design a new widget for the sidebar")
        self.assertEqual(data["suggestedMode"], "new")
        self.assertEqual(data["signals"], ["no stronger signal; default"])

    def test_suggestion_never_causes_a_nonzero_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(ORIENT, "--cwd", tmp, "--input", "")
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data["suggestedMode"], "new")


class SuggestModeTableRegressionTests(unittest.TestCase):
    """One assertion per example phrase in SKILL.md's Modes table (the
    same table architecture.md SS4 carries), with the minimal
    existingDocs/config context each phrase's own row describes it
    needing. Four of these were misses, fixed alongside this test: a
    generic change verb aimed at an unnamed doc, a critique verb with no
    doc match at all, an adopt phrase with no "promise" in it, and a bare
    ticket number with no accompanying shipped/landed/PR word."""

    # --- new: "an idea, ticket, transcript or braindump... and nothing
    # below matches" ---

    def test_new_design_this(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "design this")
        self.assertEqual(data["suggestedMode"], "new")

    def test_new_plan_this(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "plan this")
        self.assertEqual(data["suggestedMode"], "new")

    def test_new_spec_this(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "spec this")
        self.assertEqual(data["suggestedMode"], "new")

    def test_new_write_a_doc_for_x(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "write a doc for the sidebar widget")
        self.assertEqual(data["suggestedMode"], "new")

    def test_new_how_should_we_build_x(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "how should we build the sidebar widget")
        self.assertEqual(data["suggestedMode"], "new")

    # --- revise: "a path to, or the title of, an existing outcome doc
    # plus a change" ---

    def test_revise_update_with_named_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "update the Foo widget")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_add_a_rule_with_named_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "add a rule to the Foo widget doc")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_change_the_outcome_with_named_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "change the outcome for Foo widget")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_the_signal_is_wrong_with_named_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "the signal is wrong on the Foo widget doc")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_tighten_section_with_named_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "tighten section 5 of Foo widget")
        self.assertEqual(data["suggestedMode"], "revise")

    # --- revise (fixed miss): a generic change verb aimed at "the doc" /
    # "the outcome", no title named — at least one doc means revise even
    # though which doc is unnamed. ---

    def test_revise_fix_the_doc_no_title_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "fix the doc")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertTrue(any("generic change verb" in s for s in data["signals"]))

    def test_revise_update_the_doc_no_title_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "update the doc")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_change_the_outcome_no_title_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "change the outcome")
        self.assertEqual(data["suggestedMode"], "revise")

    def test_revise_generic_verb_two_docs_flags_which_doc_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(
                tmp,
                [
                    {"filename": "foo.md", "title": "Foo widget", "status": "draft"},
                    {"filename": "bar.md", "title": "Bar widget", "status": "draft"},
                ],
            )
            data = orient_with_input(tmp, "update the doc")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertTrue(any("ambiguous: which doc" in s for s in data["signals"]))

    # --- review: "a substantial doc, URL or paste authored elsewhere plus
    # a critique verb" (fixed miss: no doc match at all — pasted/external
    # content never had a rule of its own before) ---

    def test_review_please_review_this_pasted_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "please review this pasted design")
        self.assertEqual(data["suggestedMode"], "review")

    def test_review_critique_with_no_doc_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "please critique this pasted design")
        self.assertEqual(data["suggestedMode"], "review")

    def test_review_is_this_any_good(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "is this any good")
        self.assertEqual(data["suggestedMode"], "review")

    def test_review_check_this_against_the_framework(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "check this against the framework")
        self.assertEqual(data["suggestedMode"], "review")

    # --- merge: "two or more doc paths or titles" ---

    def test_merge_fold_these(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(
                tmp,
                [
                    {"filename": "foo.md", "title": "Foo widget", "status": "draft"},
                    {"filename": "bar.md", "title": "Bar widget", "status": "draft"},
                ],
            )
            data = orient_with_input(tmp, "fold these together: Foo widget and Bar widget")
        self.assertEqual(data["suggestedMode"], "merge")

    def test_merge_consolidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(
                tmp,
                [
                    {"filename": "foo.md", "title": "Foo widget", "status": "draft"},
                    {"filename": "bar.md", "title": "Bar widget", "status": "draft"},
                ],
            )
            data = orient_with_input(tmp, "consolidate Foo widget and Bar widget")
        self.assertEqual(data["suggestedMode"], "merge")

    # --- arm: "an agreed doc plus" one of five phrases ---

    def test_arm_start_building(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "Foo widget, start building")
        self.assertEqual(data["suggestedMode"], "arm")

    def test_arm_arm_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "Foo widget, arm it")
        self.assertEqual(data["suggestedMode"], "arm")

    def test_arm_write_the_red_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "Foo widget, write the red tests")
        self.assertEqual(data["suggestedMode"], "arm")

    def test_arm_file_the_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "Foo widget, file the rows")
        self.assertEqual(data["suggestedMode"], "arm")

    def test_arm_kick_off_the_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "agreed"}])
            data = orient_with_input(tmp, "Foo widget, kick off the build")
        self.assertEqual(data["suggestedMode"], "arm")

    # --- intake: "a list of complaints, wishes, bug reports or feedback
    # about the product", or "add this as a scenario to <row>" ---

    def test_intake_wishes_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "here is a list of wishes from the last call")
        self.assertEqual(data["suggestedMode"], "intake")

    def test_intake_bug_reports_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "triaging some bug reports from support")
        self.assertEqual(data["suggestedMode"], "intake")

    def test_intake_add_this_as_a_scenario_to_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [], row_id_pattern=r"^C\d+[a-z]?$")
            data = orient_with_input(tmp, "add this as a scenario to C207a")
        self.assertEqual(data["suggestedMode"], "intake")

    # --- reconcile: "a PR number, branch, commit or test file" or a
    # shipped/landed phrase (fixed miss: a bare ticket number, alone, is
    # not enough) ---

    def test_reconcile_we_shipped_x(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "we shipped the widget last week")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_reconcile_we_already_do_this(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "we already do this")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_reconcile_isnt_x_covered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "isn't the widget covered already")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_reconcile_update_the_map_now_that_y_landed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "update the map now that this landed")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_reconcile_pr_number_with_shipped_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "we already shipped this in PR #42")
        self.assertEqual(data["suggestedMode"], "reconcile")

    def test_reconcile_bare_ticket_number_with_design_words_stays_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "let's design a plan for #42")
        self.assertEqual(data["suggestedMode"], "new")
        self.assertTrue(any("ticket reference" in s for s in data["signals"]))

    def test_reconcile_bare_ticket_number_alone_stays_new(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "see #42")
        self.assertEqual(data["suggestedMode"], "new")
        self.assertTrue(any("ticket reference" in s for s in data["signals"]))

    # --- adopt: "set this project up", "install / configure promise
    # here", "add promise to CLAUDE.md" (fixed miss: an install/setup
    # verb aimed at this project with no "promise" word at all) ---

    def test_adopt_set_this_project_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "set this project up")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_adopt_install_promise_here(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "install promise here")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_adopt_configure_promise_here(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "configure promise here")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_adopt_add_promise_to_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "add promise to CLAUDE.md")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_adopt_install_it_here_no_promise_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "install it here")
        self.assertEqual(data["suggestedMode"], "adopt")

    def test_adopt_configure_it_here_no_promise_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "configure it here")
        self.assertEqual(data["suggestedMode"], "adopt")


class SuggestModeAmbiguousKeyTests(unittest.TestCase):
    """The new "ambiguous" key: true only when a lower-priority rule also
    matched with a different mode than the winner, listing that rule's
    own signal alongside the winner's. False for every single-rule match
    — including the doc-level "which doc" ambiguity, which is noted only
    as a signal string on the (unambiguous) revise mode, never as this
    key."""

    def test_false_when_only_one_rule_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "let's design a new widget for the sidebar")
        self.assertFalse(data["ambiguous"])

    def test_false_for_a_recognised_first_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, "revise the widget doc please")
        self.assertFalse(data["ambiguous"])

    def test_false_for_which_doc_ambiguity_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(
                tmp,
                [
                    {"filename": "foo.md", "title": "Foo widget", "status": "draft"},
                    {"filename": "bar.md", "title": "Bar widget", "status": "draft"},
                ],
            )
            data = orient_with_input(tmp, "update the doc")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertFalse(data["ambiguous"])

    def test_true_when_a_lower_priority_rule_matches_a_different_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            make_project(tmp, [{"filename": "foo.md", "title": "Foo widget", "status": "draft"}])
            data = orient_with_input(tmp, "update the Foo widget doc, ref PR #42 which shipped")
        self.assertEqual(data["suggestedMode"], "revise")
        self.assertTrue(data["ambiguous"])
        self.assertTrue(any("Foo widget" in s for s in data["signals"]))
        self.assertTrue(any("#42" in s for s in data["signals"]))

    def test_key_always_present_and_boolean_when_flag_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data = orient_with_input(tmp, None)
        self.assertIn("ambiguous", data)
        self.assertIsInstance(data["ambiguous"], bool)
        self.assertFalse(data["ambiguous"])


# ---------------------------------------------------------------------------
# FEATURE 2: outcome_rows.py --write-counts
# ---------------------------------------------------------------------------


class WriteCountsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.conforming_text = (FIXTURES_DIR / "conforming.md").read_text(encoding="utf-8")

    def _write(self, name: str, text: str) -> Path:
        path = self.dir / name
        path.write_bytes(text.encode("utf-8"))
        return path

    def test_wrong_count_is_corrected(self) -> None:
        wrong = self.conforming_text.replace(
            "**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).",
            "**Scenarios:** 1 acceptance rows (§6), 2 worked examples (§3).",
        )
        path = self._write("wrong.md", wrong)
        result = run(ROWS, str(path), "--write-counts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("old: ", result.stderr)
        self.assertIn("new: ", result.stderr)
        after = path.read_text(encoding="utf-8")
        self.assertIn("**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).", after)
        # nothing else on the doc changed: undoing just the count edit round-trips exactly
        self.assertEqual(after.replace("3 acceptance rows", "1 acceptance rows"), wrong)

    def test_second_run_is_byte_identical(self) -> None:
        wrong = self.conforming_text.replace(
            "**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).",
            "**Scenarios:** 1 acceptance rows (§6), 2 worked examples (§3).",
        )
        path = self._write("wrong.md", wrong)
        run(ROWS, str(path), "--write-counts")
        after_first = path.read_bytes()

        result = run(ROWS, str(path), "--write-counts")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), after_first)

    def test_still_prints_the_usual_output_to_stdout(self) -> None:
        path = self._write("conforming.md", self.conforming_text)
        result = run(ROWS, str(path), "--write-counts", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["rows"]), 3)
        self.assertEqual(data["status"], "draft")

    def test_no_scenarios_line_exits_2_with_clear_message(self) -> None:
        no_scenarios = re.sub(r"\*\*Scenarios:\*\*.*\n", "", self.conforming_text)
        self.assertNotIn("**Scenarios:**", no_scenarios)  # the fixture really has none
        path = self._write("no_scenarios.md", no_scenarios)

        result = run(ROWS, str(path), "--write-counts")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Scenarios", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_crlf_file_keeps_crlf(self) -> None:
        wrong = self.conforming_text.replace(
            "**Scenarios:** 3 acceptance rows (§6), 2 worked examples (§3).",
            "**Scenarios:** 1 acceptance rows (§6), 2 worked examples (§3).",
        )
        crlf = wrong.replace("\n", "\r\n")
        path = self.dir / "crlf.md"
        path.write_bytes(crlf.encode("utf-8"))

        result = run(ROWS, str(path), "--write-counts")
        self.assertEqual(result.returncode, 0, result.stderr)

        data = path.read_bytes()
        self.assertIn(b"\r\n", data)
        # every "\n" is part of a "\r\n" pair -- no bare LF crept in
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        self.assertTrue(data.endswith(b"\r\n"))


# ---------------------------------------------------------------------------
# FEATURE 3: outcome_rows.py --search --dir
# ---------------------------------------------------------------------------


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.search_dir = str(FOLLOWUPS_DIR / "search")

    def test_obviously_matching_row_ranks_first(self) -> None:
        result = run(ROWS, "--search", "daily digest email morning", "--dir", self.search_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertTrue(lines)
        self.assertIn("digest.md", lines[0])
        self.assertIn("AT-1", lines[0])
        self.assertIn("1.00", lines[0])

    def test_no_overlap_query_returns_no_matches_text_mode(self) -> None:
        result = run(ROWS, "--search", "zzz quokka nonexistent gibberish", "--dir", self.search_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "no matches")

    def test_no_overlap_query_returns_empty_list_json_mode(self) -> None:
        result = run(
            ROWS, "--search", "zzz quokka nonexistent gibberish", "--dir", self.search_dir, "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    def test_json_parses_and_has_the_documented_shape(self) -> None:
        result = run(ROWS, "--search", "daily digest email morning", "--dir", self.search_dir, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertTrue(data)
        for entry in data:
            self.assertEqual(set(entry.keys()), {"doc", "kind", "id", "score", "text"})
            self.assertIn(entry["kind"], ("row", "rule"))

    def test_top_8_cap_and_ordering_is_stable_across_both_docs(self) -> None:
        result = run(ROWS, "--search", "archived channel digest", "--dir", self.search_dir, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertLessEqual(len(data), 8)
        scores = [entry["score"] for entry in data]
        self.assertEqual(scores, sorted(scores, reverse=True))


# ---------------------------------------------------------------------------
# -h documents the new flags
# ---------------------------------------------------------------------------


class HelpDocumentsNewFlagsTests(unittest.TestCase):
    def test_orient_help_documents_input(self) -> None:
        result = run(ORIENT, "-h")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--input", result.stdout)

    def test_outcome_rows_help_documents_write_counts_and_search(self) -> None:
        result = run(ROWS, "-h")
        self.assertEqual(result.returncode, 0)
        self.assertIn("--write-counts", result.stdout)
        self.assertIn("--search", result.stdout)
        self.assertIn("--dir", result.stdout)


if __name__ == "__main__":
    unittest.main()
