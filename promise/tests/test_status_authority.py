"""Locks the skill's status-authority rule: `agreed` and `shipped` are typed
by a human, never by this skill; `building` is the one exception, written by
`arm` only after the human has confirmed the red-gate commit.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Checks, matching the ways this rule could quietly stop holding:
(a) arm.md still states the step and names itself the only writer; (b)
SKILL.md still states the rule in the open; (c) every line anywhere under
skills/promise/ that mentions moving a doc to `agreed` or `shipped` also
names the human actor -- an inventory over every such line, not a fixed
phrase list a rewording could slip past; (d) the lint rule that makes
`building` checkable -- BUILDING_NEEDS_GATE -- fires as an ERROR on a
`building` doc with no red-gate commit line in its header, is not fooled by
a hex-looking run elsewhere in the header, accepts a digit-only sha, and
clears once a real `Red gate: <sha> <date>` line is added.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SKILL = TESTS_DIR.parent / "skills" / "promise"
SCRIPTS_DIR = SKILL / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"

ARM_MD = SKILL / "modes" / "arm.md"
SKILL_MD = SKILL / "SKILL.md"
BUILDING_NO_GATE = FIXTURES_DIR / "building_no_gate.md"

# A line instructing something to write/set/flip/mark/move/change a doc TO
# `agreed`/`shipped` must also name the actor: only a line naming `human`
# passes. Bare co-occurrence of a status word and a verb on one line is too
# coarse against real prose — "cannot move to `agreed`" (a precondition, not
# an instruction), "the code shipped" (a colloquial past tense), "a verdict
# moves" (a different subject entirely) all share a line with one of these
# words for reasons that have nothing to do with who writes the doc's own
# `Status:` field. So a match requires the verb and the status word within a
# short same-clause gap (no `.`, `;`, `→` in between — those end the clause),
# in EITHER order — "write `Status: X`" and "`X` ... human-typed" are both
# real phrasings this skill uses — while a negation immediately before the
# verb ("cannot move") or a new subject introduced in the gap ("and a
# verdict moves") is excluded. This still catches a genuine rewording:
# "change `Status:` to `shipped`", "flip it to `agreed`", "mark it
# `shipped`" all match (see DetectorSelfTest below).
STATUS_WORD = r"(?:agreed|shipped)"
TRANSITION_VERB = r"(?:write|writes|set|sets|flip|flips|mark|marks|move|moves|change|changes|typed)"
GAP = r"[^.\n;→]{0,30}?"
NEGATION_RE = re.compile(r"\b(cannot|can't|never|not|n't|won't|shouldn't|don't|doesn't|no)\b", re.IGNORECASE)
NEW_CLAUSE_RE = re.compile(r"\band (?:a|an|the)\b", re.IGNORECASE)
FORWARD_RE = re.compile(
    rf"(?P<neg>\b(?:cannot|can't|never|not|n't|won't|shouldn't|don't|doesn't|no)\b\s+)?"
    rf"\b(?P<verb>{TRANSITION_VERB})\b(?P<gap>{GAP})`?(?:status:?\s*)?`?\b(?P<status>{STATUS_WORD})\b",
    re.IGNORECASE,
)
BACKWARD_RE = re.compile(
    rf"`?\b(?P<status>{STATUS_WORD})\b`?(?P<gap>{GAP})\b(?P<verb>{TRANSITION_VERB})\b",
    re.IGNORECASE,
)
HUMAN_RE = re.compile(r"\bhuman\b", re.IGNORECASE)


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


def transition_matches(line: str) -> List[str]:
    """Every substring of `line` that reads as an instruction to move a doc
    TO `agreed`/`shipped` (see the constants above for what is excluded and
    why). Empty when the line has no such instruction on it at all."""
    out = []
    for m in FORWARD_RE.finditer(line):
        if m.group("neg") or NEW_CLAUSE_RE.search(m.group("gap")):
            continue
        out.append(m.group(0))
    for m in BACKWARD_RE.finditer(line):
        if NEW_CLAUSE_RE.search(m.group("gap")):
            continue
        out.append(m.group(0))
    return out


def status_transition_lines(text: str) -> List[Tuple[int, str]]:
    """(1-based line number, raw line text) for every line carrying at
    least one match from `transition_matches`."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if transition_matches(line):
            out.append((i, line))
    return out


def lint_json(path: Path, *args: str) -> Tuple[subprocess.CompletedProcess, Optional[dict]]:
    result = subprocess.run(
        [sys.executable, str(LINT), str(path), "--json", *args],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


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


class OnlyAHumanMovesAgreedOrShipped(unittest.TestCase):
    """Inventory check, not a fixed phrase list: every line anywhere under
    skills/promise/ that talks about moving a doc to `agreed`/`shipped`
    must name `human` as the actor on that same line. A rewording
    ("change `Status:` to `shipped`", "flip it to agreed") is still caught,
    because the check is about what the line SAYS, not which of six exact
    strings it happens to contain."""

    def test_every_status_transition_line_names_the_human_actor(self) -> None:
        checked = 0
        for path in skill_prose_files():
            text = path.read_text(encoding="utf-8")
            for line_no, line in status_transition_lines(text):
                checked += 1
                # Asserted individually, one subTest per line, rather than
                # batched into one pass/fail: a run naming which specific
                # file:line lacks `human` (not just that "something" did)
                # is what actually tells a reader what to go fix.
                with self.subTest(file=str(path.relative_to(SKILL)), line=line_no):
                    self.assertRegex(
                        line,
                        HUMAN_RE,
                        f"{path.relative_to(SKILL)}:{line_no} mentions moving to agreed/shipped "
                        f"without naming the human actor: {line.strip()!r}",
                    )

        # A scan that found zero transition lines anywhere would make every
        # subTest above vacuous — the rule IS stated in arm.md/SKILL.md, so
        # at least one line must have matched, or this test proves nothing
        # about a rewording that removes `human` from all of them.
        self.assertGreater(checked, 0, "no status-transition line was found under skills/promise/ to check")

    def test_every_prose_file_was_actually_scanned(self) -> None:
        # A file-collection bug that silently scans zero files would make
        # the test above vacuous. Pin a floor: SKILL.md, outcome-framework.md,
        # 8 modes, at least 4 references, at least 1 template.
        files = skill_prose_files()
        self.assertIn(SKILL_MD, files)
        self.assertIn(SKILL / "outcome-framework.md", files)
        self.assertGreaterEqual(len(list((SKILL / "modes").glob("*.md"))), 8)
        self.assertGreaterEqual(len(files), 14)


class DetectorSelfTest(unittest.TestCase):
    """Positive and negative controls for transition_matches/HUMAN_RE, run
    against fixed strings rather than the live docs — a phrase list would
    miss every rewording below; a docs edit could accidentally make the
    scan above vacuous either way. Pin both directions so a regression in
    the regex itself, not just in the docs, is caught here."""

    # Real bypass phrasings the check must catch (none names `human`).
    BYPASSES = (
        "Then change `Status:` to `shipped` once the suite is green.",
        "Flip it to `agreed` once you're happy.",
        "Mark it `shipped`.",
    )

    # Lines drawn from the skill's own docs that mention `agreed`/`shipped`
    # near one of the transition verbs for reasons unrelated to who writes
    # the field — a precondition, a colloquial past tense, an unrelated
    # subject. None of these may match at all.
    NON_INSTRUCTIONS = (
        '| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", '
        '"arm it", "write the red tests", "file the rows", "kick off the build" |',
        "A doc in `draft` with unresolved BLOCKING questions cannot move to `agreed`.",
        "Set `Status: draft` on the survivor, even where a folded doc was `agreed`",
        "Doc is `agreed` or later → a §0 change un-ratifies it.",
        "A PR merging says the code shipped, not that the test was watched — "
        "the verdict moves when the evidence reaches the `Then`'s altitude.",
        "after `agreed` and a verdict moves only at the altitude the row's own `Then` claims;",
        "after a doc is `agreed`. A verdict moves only when evidence reaches the altitude",
    )

    TRUE_POSITIVE = "it records — say so in the close-out. `agreed` and `shipped` stay human-typed."

    def test_catches_every_bypass_phrasing(self) -> None:
        for bypass in self.BYPASSES:
            with self.subTest(line=bypass):
                found = transition_matches(bypass)
                self.assertTrue(found, f"detector missed a real bypass: {bypass!r}")
                self.assertFalse(
                    HUMAN_RE.search(bypass),
                    f"fixture is not actually a bypass — it already names human: {bypass!r}",
                )

    def test_does_not_flag_unrelated_prose(self) -> None:
        for line in self.NON_INSTRUCTIONS:
            with self.subTest(line=line):
                found = transition_matches(line)
                self.assertEqual(found, [], f"false positive on unrelated prose: {line!r}")

    def test_recognises_the_human_typed_phrasing(self) -> None:
        found = transition_matches(self.TRUE_POSITIVE)
        self.assertTrue(found, "detector must still recognise the skill's own correct phrasing")
        self.assertTrue(HUMAN_RE.search(self.TRUE_POSITIVE))


class BuildingNeedsGateRule(unittest.TestCase):
    def test_fixture_exists(self) -> None:
        self.assertTrue(BUILDING_NO_GATE.is_file(), "missing fixture: building_no_gate.md")

    def _write(self, tmp: str, text: str) -> Path:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_fires_as_an_error_with_no_red_gate_commit(self) -> None:
        proc, data = lint_json(BUILDING_NO_GATE)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1, data["findings"])
        self.assertEqual(findings[0]["severity"], "error")
        # No other error-severity rule fires alongside it: the fixture is
        # conforming.md with Status: building and every rule tagged.
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["BUILDING_NEEDS_GATE"])

    def test_strict_has_no_additional_effect(self) -> None:
        # Already an error: --strict (which only promotes warn -> error)
        # changes nothing about it.
        proc, data = lint_json(BUILDING_NO_GATE, "--strict")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "error")

    def test_clears_once_a_red_gate_commit_is_in_the_header(self) -> None:
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        with_gate = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1
        )
        self.assertNotEqual(with_gate, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, with_gate))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertNotIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_digit_only_sha_is_valid(self) -> None:
        # The regex's sha group is [0-9a-fA-F]{7,40} -- digits alone qualify.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        with_gate = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: 1234567 2026-01-02\n", 1
        )
        self.assertNotEqual(with_gate, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, with_gate))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertNotIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_hex_word_elsewhere_in_the_header_does_not_satisfy_the_rule(self) -> None:
        # False positive: a hex-looking run on a DIFFERENT header line (not
        # its own `Red gate:` line) must never quietly clear the rule.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        mutated = text.replace("Supersedes: —\n", "Supersedes: deadbeef\n", 1)
        self.assertNotEqual(mutated, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, mutated))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_digit_only_date_elsewhere_does_not_satisfy_the_rule(self) -> None:
        # False positive: an un-hyphenated digit run (e.g. a Last decision:
        # date with no dashes) must never quietly clear the rule either.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        mutated = text.replace("Last decision: 2026-01-01", "Last decision: 20260101", 1)
        self.assertNotEqual(mutated, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, mutated))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_conforming_and_template_still_lint_clean(self) -> None:
        # A rule this specific must not fire on either baseline fixture —
        # conforming.md is Status: draft, and the template is exempted via
        # --template, so neither carries Status: building at all.
        proc, conforming = lint_json(FIXTURES_DIR / "conforming.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
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
