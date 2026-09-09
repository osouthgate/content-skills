"""Locks the skill's status-authority rule: `agreed` and `shipped` are typed
by a human, never by this skill; `building` is the one exception, written by
`arm` only after the human has confirmed the red-gate commit.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

Checks, matching the ways this rule could quietly stop holding:
(a) arm.md still states the step and names itself the only writer; (b)
SKILL.md still states the rule in the open; (c) every sentence anywhere
under skills/promise/ that mentions `agreed`/`shipped` alongside a
status-transition verb is checked against a FROZEN ALLOWLIST, not a
heuristic — a heuristic can always be bypassed (a rewording it wasn't built
for) or false-positive (unrelated prose it wasn't built to exclude); the
collector here is deliberately broad instead, and a human decides, once,
which of what it finds are real; (d) the lint rule that makes `building`
checkable — BUILDING_NEEDS_GATE — fires as an ERROR on a `building` doc with
no red-gate commit line in its unfenced header, is not fooled by a
hex-looking run elsewhere in the header, a fenced illustration, or an
impossible calendar date, accepts a digit-only sha, and clears once a real
`Red gate: <sha> <date>` line is added.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SKILL = TESTS_DIR.parent / "skills" / "promise"
SCRIPTS_DIR = SKILL / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"

ARM_MD = SKILL / "modes" / "arm.md"
SKILL_MD = SKILL / "SKILL.md"
BUILDING_NO_GATE = FIXTURES_DIR / "building_no_gate.md"


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including a line-wrap plus the next
    line's indentation) to one space, so a "literal" phrase check matches
    prose that markdown wraps across lines the same way a reader sees it —
    the wrap column is a formatting choice, not part of what the doc says."""
    return re.sub(r"\s+", " ", text)


def skill_prose_files() -> List[Path]:
    """SKILL.md, modes/*.md, references/*.md, outcome-framework.md, templates/*.md."""
    files = [SKILL_MD, SKILL / "outcome-framework.md"]
    files += sorted((SKILL / "modes").glob("*.md"))
    files += sorted((SKILL / "references").glob("*.md"))
    files += sorted((SKILL / "templates").glob("*.md"))
    return [f for f in files if f.is_file()]


def lint_json(path: Path, *args: str) -> Tuple[subprocess.CompletedProcess, Optional[dict]]:
    result = subprocess.run(
        [sys.executable, str(LINT), str(path), "--json", *args],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


# ---------------------------------------------------------------------------
# The status-transition collector — deliberately broad, no negation or
# clause logic at all. A heuristic that tries to be clever about what
# counts as "really" an instruction is exactly what a rewording bypasses
# and unrelated prose false-positives on; this one does neither, on
# purpose, and leaves the judgement to the frozen allowlist below.
# ---------------------------------------------------------------------------

STATUS_WORD_RE = re.compile(r"\b(agreed|shipped)\b", re.IGNORECASE)
TRANSITION_VERB_RE = re.compile(
    r"\b(write|writes|written|set|sets|flip|flips|mark|marks|move|moves|"
    r"change|changes|type|typed|types|advance|advances|promote|promotes|"
    r"reach|reaches|becomes)\b",
    re.IGNORECASE,
)
_LIST_MARKER_RE = re.compile(r"^([-*]|\d+\.)\s+")


def logical_sentences(text: str) -> List[str]:
    """Markdown line-wraps collapsed into logical paragraphs, then split
    into sentences.

    A new paragraph starts at a blank line, a heading, a table row, a
    fence line, or a list-item marker; every other line continues the
    current paragraph (this is how a wrapped sentence — "cannot move to\\n
    `agreed`." — is seen as one piece of text, the way a reader sees it,
    not two unrelated lines). Each paragraph is then split into sentences
    on a period followed by whitespace or the paragraph's end. This is
    presentation unwrapping, not a grammar parser — an abbreviation would
    over-split, which only ever produces a smaller, still-checked
    fragment, never a missed one.
    """
    paragraphs: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(re.sub(r"\s+", " ", " ".join(current)).strip())
            current.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush()
            continue
        starts_new = (
            stripped.startswith("#")
            or stripped.startswith("|")
            or stripped.startswith("```")
            or stripped.startswith("~~~")
            or bool(_LIST_MARKER_RE.match(stripped))
        )
        if starts_new:
            flush()
        current.append(stripped)
    flush()

    sentences: List[str] = []
    for para in paragraphs:
        for piece in re.split(r"(?<=[.])\s+", para):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def is_status_transition_sentence(sentence: str) -> bool:
    """True when `sentence` names `agreed`/`shipped` (with or without
    backticks — `\\b` does not care either way) AND any transition verb,
    anywhere in the sentence, in any order. No negation check, no clause
    check, no proximity requirement: deliberately broad."""
    return bool(STATUS_WORD_RE.search(sentence) and TRANSITION_VERB_RE.search(sentence))


def collect_status_transition_sentences() -> Dict[str, List[str]]:
    """sentence text -> the files it was found in (usually one; the `arm`
    mode-dispatch row is documented verbatim in two places). Every
    sentence collected here must be a key in STATUS_TRANSITION_ALLOWLIST
    below, and every key in that allowlist must show up here — see
    StatusTransitionAllowlistTests.
    """
    found: Dict[str, List[str]] = {}
    for path in skill_prose_files():
        text = path.read_text(encoding="utf-8")
        for sentence in logical_sentences(text):
            if is_status_transition_sentence(sentence):
                found.setdefault(sentence, []).append(str(path.relative_to(SKILL)))
    return found


# ---------------------------------------------------------------------------
# The frozen allowlist. Every sentence collect_status_transition_sentences()
# finds under skills/promise/ today, each with why it is not an instruction
# for THIS SKILL to write `agreed`/`shipped` itself:
#
#   human-actor              -- names a human as the one who does it, as a rule
#   describes-the-human-act  -- narrates the human act in passing, not as a rule
#   negated                  -- describes when the transition is NOT allowed
#   not-a-transition         -- the verb and the status word are unrelated here
#
# A sentence the collector finds that is not a key here fails the test: a
# human must read it and either add it, with a reason, or reword the doc so
# it no longer reads as a status-transition instruction. A key here that the
# collector no longer finds anywhere also fails — a stale entry would hide a
# doc change from review just as surely as a missing one would.
# ---------------------------------------------------------------------------

STATUS_TRANSITION_ALLOWLIST: Dict[str, str] = {
    "Where the project configures a capability map, the map becomes the "
    "source of the doc's scenarios from the moment a human marks the doc "
    "`agreed` — the doc's acceptance rows are filed there as rows, and "
    "`intake`/`reconcile` read and write the map, not a second copy inside "
    "the doc.": "describes-the-human-act",

    '| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", '
    '"arm it", "write the red tests", "file the rows", "kick off the '
    'build" |': "not-a-transition",

    "- `agreed` and `shipped` are typed by a human, never by this skill.":
        "human-actor",

    "- A doc in `draft` with unresolved BLOCKING questions cannot move to "
    "`agreed`.": "negated",

    "Write the new row id into the `Row` column of each §6 line it "
    "covers, and add one line under the §6 table: `Snapshot taken at "
    "`agreed` on <date>; the map is the source of these scenarios from "
    "here on.` §0's rule tags stay AT aliases; they do not change.":
        "not-a-transition",

    "`agreed` and `shipped` stay human-typed.": "human-actor",

    "- Set `Status: draft` on the survivor, even where a folded doc was "
    "`agreed` or later — the merge is a new draft until the human "
    "re-ratifies it.": "not-a-transition",

    "**The human flips `Status: shipped`, never this mode.**": "human-actor",

    "- Doc is `agreed` or later → a §0 change un-ratifies it.":
        "not-a-transition",

    "| \"Status agreed is a formality, I'll flip it.\" | It's the human "
    "act the whole framework protects.": "describes-the-human-act",

    "Where the project keeps a **capability map** — a machine-checked "
    "register of promises and the tests that prove them — the doc's "
    "acceptance rows become **rows** in that map when the doc is "
    "`agreed`, and the map becomes the source of the scenarios from then "
    "on.": "not-a-transition",

    "| `shipped` | Human flips it when §6 rows are green.": "human-actor",

    "`agreed` and `shipped` are typed by a human.": "human-actor",

    "The rendered block is ≤ 20 lines and says: capability work goes "
    "through `/promise` in plain words (the mode is inferred); one doc "
    "per capability in the docs home, in the Outcome Framework shape; §0 "
    "is the human's verbatim block and agents only append notes below "
    "it; `Status:` moves forward only by a human; where a map is "
    "configured it is the source of scenarios after `agreed` and a "
    "verdict moves only at the altitude the row's own `Then` claims; "
    "before writing any design, plan or spec doc by hand, run `/promise` "
    "— a sibling doc is a bug.": "human-actor",

    "No mode file restates a project's mechanics; each says \"read the "
    "recipe, work from the file.\" Look in the recipe for the parts a "
    "mode will ask for by name: a **routing table** (which relation a "
    "piece of feedback becomes), the **lockstep rule** (which files move "
    "together, and in what order), a **lane table** (how a `Then`'s "
    "altitude picks a test kind), a **verification block** (the commands "
    "to run before calling anything done), and a **shipped-work "
    "section** — the mirror direction, code landed and a row needs "
    "updating.": "not-a-transition",

    "- `Status:` reaches `agreed` and `shipped` only by a human's hand; "
    "`building` only after the human approves the red-test commit.":
        "human-actor",
}


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


class StatusTransitionAllowlistTests(unittest.TestCase):
    """(c): every collected sentence must be allowlisted; every allowlisted
    sentence must still be collected. Both directions are load-bearing —
    the first catches a new bypass-shaped sentence, the second catches an
    allowlist that has quietly gone stale and stopped meaning anything."""

    def test_every_collected_sentence_is_allowlisted(self) -> None:
        collected = collect_status_transition_sentences()
        unlisted = [s for s in collected if s not in STATUS_TRANSITION_ALLOWLIST]
        self.assertEqual(
            unlisted,
            [],
            "new status-transition sentence — a human must read it and add it to "
            "the allowlist, or reword it:\n\n"
            + "\n\n".join(f"{s!r}\n  found in: {', '.join(collected[s])}" for s in unlisted),
        )

    def test_every_allowlist_entry_still_exists(self) -> None:
        collected = collect_status_transition_sentences()
        stale = [s for s in STATUS_TRANSITION_ALLOWLIST if s not in collected]
        self.assertEqual(
            stale,
            [],
            "allowlisted sentence no longer found anywhere under skills/promise/ "
            "(a stale entry hides a doc change from review):\n\n"
            + "\n\n".join(repr(s) for s in stale),
        )

    def test_allowlist_reasons_are_one_of_the_four_words(self) -> None:
        allowed_reasons = {"human-actor", "describes-the-human-act", "negated", "not-a-transition"}
        for sentence, reason in STATUS_TRANSITION_ALLOWLIST.items():
            with self.subTest(sentence=sentence[:60]):
                self.assertIn(reason, allowed_reasons, f"{reason!r} is not one of {allowed_reasons}")

    def test_collector_found_at_least_one_sentence(self) -> None:
        # A collector that silently finds nothing would make both checks
        # above vacuous — the rule IS stated in arm.md/SKILL.md, so at
        # least one sentence must be found.
        collected = collect_status_transition_sentences()
        self.assertGreater(len(collected), 0, "no status-transition sentence was found at all")


class CollectorUnitProbes(unittest.TestCase):
    """A heuristic detector was bypassable and had false positives (a prior
    Codex re-review finding); these three fixed phrasings are the proof —
    the deliberately broad collector above must COLLECT all three (whether
    they are ALLOWED is the allowlist's job, and none of them is in it,
    since none exists in the real docs today)."""

    PROBES = (
        # Bypassed a "does the line also say human" check: `human` appears,
        # but not as the actor of the write.
        "Set Status: shipped without human approval.",
        # False-positived a negation/clause heuristic: this sentence STATES
        # the rule correctly (the skill never sets it) but was flagged as
        # if it were the violation.
        "`shipped` should never be set by the skill.",
        # Missed by a heuristic requiring the verb and the status word
        # within a short gap or a specific order.
        "Change the status and the document state to shipped.",
    )

    def test_all_three_probes_are_collected(self) -> None:
        for probe in self.PROBES:
            with self.subTest(probe=probe):
                self.assertTrue(
                    is_status_transition_sentence(probe),
                    f"the broad collector must catch this phrasing: {probe!r}",
                )

    def test_none_of_the_probes_is_allowlisted(self) -> None:
        for probe in self.PROBES:
            with self.subTest(probe=probe):
                self.assertNotIn(
                    probe, STATUS_TRANSITION_ALLOWLIST,
                    f"probe should not already exist in the real docs: {probe!r}",
                )


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
        # A real line directly under `Supersedes:` clears the rule.
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

    def test_fenced_red_gate_line_does_not_clear_the_rule(self) -> None:
        # A Red gate: line sitting inside a fenced code block (an
        # illustration, not the doc's own header) must not clear the rule.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        fenced = text.replace(
            "Supersedes: —\n",
            "Supersedes: —\n```\nRed gate: a1b2c3d 2026-01-02\n```\n",
            1,
        )
        self.assertNotEqual(fenced, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, fenced))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])
        finding = next(f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE")
        self.assertIn("none found", finding["message"])

    def test_tilde_fenced_red_gate_line_does_not_clear_the_rule(self) -> None:
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        fenced = text.replace(
            "Supersedes: —\n",
            "Supersedes: —\n~~~\nRed gate: a1b2c3d 2026-01-02\n~~~\n",
            1,
        )
        self.assertNotEqual(fenced, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, fenced))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_impossible_date_fires_its_own_message(self) -> None:
        # A line matching the sha/date SHAPE but naming a date that does
        # not exist on the calendar is its own finding, not silently
        # treated as no line at all.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        bad_date = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-02-31\n", 1
        )
        self.assertNotEqual(bad_date, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, bad_date))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1, data["findings"])
        self.assertEqual(findings[0]["severity"], "error")
        self.assertIn("not a real calendar date", findings[0]["message"])
        self.assertIn("2026-02-31", findings[0]["message"])

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
