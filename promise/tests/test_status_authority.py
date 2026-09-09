"""Locks the skill's status-authority rule: `agreed` and `shipped` are typed
by a human, never by this skill; `building` is the one exception, written by
`arm` only after the human has confirmed the red-gate commit.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Four checks, matching the four ways this rule could quietly stop holding:
(a) arm.md still states the step and names itself the only writer; (b)
SKILL.md still states the rule in the open; (c) no file under skills/promise/
contains an instruction for the skill to write `agreed` or `shipped` itself;
(d) the lint rule that makes `building` checkable — BUILDING_NEEDS_GATE —
fires on a `building` doc with no red-gate commit in its header, and clears
once one is added.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SKILL = TESTS_DIR.parent / "skills" / "promise"
SCRIPTS_DIR = SKILL / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"

ARM_MD = SKILL / "modes" / "arm.md"
SKILL_MD = SKILL / "SKILL.md"
BUILDING_NO_GATE = FIXTURES_DIR / "building_no_gate.md"

# Every string that would mean this skill writes `agreed` or `shipped`
# itself, in any file under skills/promise/. The literal quote character
# used in the skill's own prose is a backtick, so these are checked
# literally rather than case- or quote-insensitively — a paraphrase that
# reads the same to a person but uses different words would not (and should
# not) be caught here; this is a lock on the skill's own stated instructions,
# not a full-coverage scan for every possible way to say it.
FORBIDDEN_WRITE_PHRASES = (
    "write `Status: agreed`",
    "write `Status: shipped`",
    "writes `agreed`",
    "writes `shipped`",
    "set Status: agreed",
    "set Status: shipped",
)


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including a line-wrap plus the next
    line's indentation) to one space, so a "literal" phrase check matches
    prose that markdown wraps across lines the same way a reader sees it —
    the wrap column is a formatting choice, not part of what the doc says."""
    return re.sub(r"\s+", " ", text)


def skill_prose_files():
    """SKILL.md, modes/*.md, references/*.md, outcome-framework.md, templates/*.md."""
    files = [SKILL_MD, SKILL / "outcome-framework.md"]
    files += sorted((SKILL / "modes").glob("*.md"))
    files += sorted((SKILL / "references").glob("*.md"))
    files += sorted((SKILL / "templates").glob("*.md"))
    return [f for f in files if f.is_file()]


def lint_json(path: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(LINT), str(path), "--json", *args],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class ArmWritesOnlyBuilding(unittest.TestCase):
    def test_arm_states_the_step_text(self) -> None:
        text = normalize_whitespace(ARM_MD.read_text(encoding="utf-8"))
        self.assertIn(
            "Ask, then write `Status: building`",
            text,
            "arm.md must state the confirm-then-write step for `building`",
        )

    def test_arm_states_it_is_the_only_status_this_skill_writes(self) -> None:
        text = normalize_whitespace(ARM_MD.read_text(encoding="utf-8"))
        self.assertIn(
            "This is the only status this skill writes",
            text,
            "arm.md must say `building` is the only status this skill writes",
        )


class SkillStatesTheRule(unittest.TestCase):
    def test_skill_md_states_typed_by_a_human(self) -> None:
        text = normalize_whitespace(SKILL_MD.read_text(encoding="utf-8"))
        self.assertIn("typed by a human", text)


class NoFileInstructsWritingTheOtherTwoStatuses(unittest.TestCase):
    def test_no_forbidden_phrase_anywhere_under_skills_promise(self) -> None:
        hits = []
        for path in skill_prose_files():
            text = normalize_whitespace(path.read_text(encoding="utf-8"))
            for phrase in FORBIDDEN_WRITE_PHRASES:
                if phrase in text:
                    hits.append(f"{path.relative_to(SKILL)}: {phrase!r}")
        self.assertEqual(
            hits,
            [],
            "an instruction to write `agreed`/`shipped` was found where only a human may:\n"
            + "\n".join(hits),
        )

    def test_every_prose_file_was_actually_scanned(self) -> None:
        # A file-collection bug that silently scans zero files would make
        # the test above vacuous. Pin a floor: SKILL.md, outcome-framework.md,
        # 8 modes, at least 4 references, at least 1 template.
        files = skill_prose_files()
        self.assertIn(SKILL_MD, files)
        self.assertIn(SKILL / "outcome-framework.md", files)
        self.assertGreaterEqual(len(list((SKILL / "modes").glob("*.md"))), 8)
        self.assertGreaterEqual(len(files), 14)


class BuildingNeedsGateRule(unittest.TestCase):
    def test_fixture_exists(self) -> None:
        self.assertTrue(BUILDING_NO_GATE.is_file(), "missing fixture: building_no_gate.md")

    def test_fires_as_a_warning_with_no_red_gate_commit(self) -> None:
        data = lint_json(BUILDING_NO_GATE)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules)
        finding = next(f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE")
        self.assertEqual(finding["severity"], "warn")
        # No other error-severity rule should fire alongside it: the fixture
        # is conforming.md with Status: building and every rule tagged.
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, [])

    def test_strict_promotes_it_to_error(self) -> None:
        data = lint_json(BUILDING_NO_GATE, "--strict")
        finding = next(f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE")
        self.assertEqual(finding["severity"], "error")

    def test_clears_once_a_red_gate_commit_is_in_the_header(self) -> None:
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        with_gate = text.replace(
            "Supersedes: —\n",
            "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n",
            1,
        )
        self.assertNotEqual(with_gate, text)
        self.assertIn("Red gate: a1b2c3d 2026-01-02", with_gate)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "with_gate.md"
            path.write_text(with_gate, encoding="utf-8")
            data = lint_json(path)
            rules = [f["rule"] for f in data["findings"]]
            self.assertNotIn("BUILDING_NEEDS_GATE", rules)

    def test_conforming_and_template_still_lint_clean(self) -> None:
        # A rule this specific must not fire on either baseline fixture —
        # conforming.md is Status: draft, and the template is exempted via
        # --template, so neither carries Status: building at all.
        conforming = lint_json(FIXTURES_DIR / "conforming.md")
        self.assertEqual(conforming["stats"], {"errors": 0, "warnings": 0, "total": 0})

        template = SKILL / "templates" / "outcome-doc.md"
        result = subprocess.run(
            [sys.executable, str(LINT), str(template), "--template"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
