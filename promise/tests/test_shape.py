"""Shape tests for the promise skill itself.

These enforce the rules `references/architecture.md` states for the skill's own files:
line budgets, the three-line header on every mode file, relative links that resolve,
no project-specific leakage, a valid example config, and a template that passes the
lint. A rule that lives only in a spec drifts; a rule with a test does not.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skills" / "promise"

MODES = ["new", "revise", "review", "merge", "arm", "intake", "reconcile", "adopt"]
REFERENCES_BUDGETED = ["slates.md", "altitude.md", "anti-rationalizations.md", "config.md"]
HEADER_LINES = ("Read before this:", "Phase 0 line:", "Writes:")
LEAK_WORDS = re.compile(
    r"\b(Loam|LoamDB|Ollie|Andy|osdb|brockenhurst|GATEKEEPER|KEYMASTER|Convex|getloam)\b"
)
ROW_ID = re.compile(r"\bC\d{1,3}[a-z]?\b")
HISTORY = re.compile(
    r"\bpredecessor\b|`outcome`(?! doc)|\boutcome (plugin|skill)\b|\b(field|trial) finding\b|"
    r"\bpreviously\b|\bthe old\b|\bwe (found|observed|learned)\b|\bthis (said|read) \b|"
    r"\balready drifted\b|\bdrifted once\b|\bwas caught\b|\bobserved in practice\b|\bthe reference project\b",
    re.IGNORECASE,
)
YEAR = re.compile(r"\b20[2-9]\d-\d\d-\d\d\b")
REL_LINK = re.compile(r"(?<![\w/])(modes|references|templates|scripts)/[A-Za-z0-9_.-]+")


def lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


class Budgets(unittest.TestCase):
    def test_router_is_thin(self) -> None:
        n = lines(SKILL / "SKILL.md")
        self.assertLessEqual(n, 150, f"SKILL.md is {n} lines; the router budget is 150")

    def test_mode_files_within_budget(self) -> None:
        for m in MODES:
            n = lines(SKILL / "modes" / f"{m}.md")
            self.assertLessEqual(n, 220, f"modes/{m}.md is {n} lines; budget 220")

    def test_reference_files_within_budget(self) -> None:
        for r in REFERENCES_BUDGETED:
            n = lines(SKILL / "references" / r)
            self.assertLessEqual(n, 220, f"references/{r} is {n} lines; budget 220")


class ModeHeaders(unittest.TestCase):
    def test_every_mode_has_the_three_line_header(self) -> None:
        for m in MODES:
            text = SKILL.joinpath("modes", f"{m}.md").read_text(encoding="utf-8")
            for h in HEADER_LINES:
                self.assertIn(h, text, f"modes/{m}.md lacks the header line '{h}'")


class Preamble(unittest.TestCase):
    """The load-time orient line must not be able to abort the skill: a host with
    no `python3` on PATH reaches the fallback paragraph only if the line ends in
    `|| true` and its stderr lands in the block."""

    def test_orient_preamble_cannot_abort_the_skill(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            '!`python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py" 2>&1 || true`',
            text,
            "SKILL.md's Phase 0 preamble must end in `2>&1 || true`",
        )
        self.assertIn("`py -3`", text, "the fallback paragraph must name the `py -3` spelling")


def flat(path: Path) -> str:
    """Whitespace-normalised file text, so a phrase check matches prose that
    markdown wraps across lines the same way a reader sees it."""
    return " ".join(path.read_text(encoding="utf-8").split())


class SnapshotRule(unittest.TestCase):
    """A bridged §6 is a snapshot; the modes that edit or judge a doc must say so
    and run the bridge check rather than trusting the lint alone."""

    def test_revise_treats_a_bridged_section_six_as_a_snapshot(self) -> None:
        text = flat(SKILL / "modes" / "revise.md")
        self.assertIn("§6 is a snapshot", text)
        self.assertIn("never edit the table", text)
        self.assertNotIn("§5, §6, §7", text, "§6 must not sit in the freely-editable list")

    def test_revise_review_and_reconcile_run_bridge_validate(self) -> None:
        for m in ("revise", "review", "reconcile"):
            with self.subTest(mode=m):
                self.assertIn("scripts/bridge_validate.py", flat(SKILL / "modes" / f"{m}.md"))

    def test_a_section_zero_change_on_a_bridged_doc_names_the_map_rows(self) -> None:
        text = flat(SKILL / "modes" / "revise.md")
        self.assertIn("name the map rows", text)


CHECKS_CALL = re.compile(r'adapter\.py"? checks')


class HandBackSequence(unittest.TestCase):
    """arm, intake and reconcile hand back the same way: `adapter.py checks` only
    when a map is configured, `verify` only when commands are, the lint always."""

    def test_checks_is_guarded_on_a_configured_map(self) -> None:
        seen = 0
        for m in MODES:
            text = flat(SKILL / "modes" / f"{m}.md")
            if not CHECKS_CALL.search(text):
                continue
            seen += 1
            with self.subTest(mode=m):
                self.assertIn("checks` if a map is configured", text)
        self.assertGreaterEqual(seen, 3, "arm, intake and reconcile all run adapter.py checks")

    def test_the_three_writing_hand_backs_verify_and_lint(self) -> None:
        for m in ("arm", "intake", "reconcile"):
            text = flat(SKILL / "modes" / f"{m}.md")
            with self.subTest(mode=m):
                self.assertIn("verify", text)
                self.assertIn("lint_outcome.py", text)
                self.assertIn("commands.*` is configured", text)


SCORE = re.compile(r"completeness score|\b\d{1,2}/10\b")


class HouseStyleNotShipped(unittest.TestCase):
    """The recommendation discipline ships; the author's private numeric
    completeness score and the mandatory reading assignment do not."""

    def test_no_numeric_completeness_scores(self) -> None:
        hits = []
        for p in SKILL.rglob("*.md"):
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if SCORE.search(line):
                    hits.append(f"{p.relative_to(SKILL)}:{i}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "numeric completeness scores must not be mandated:\n" + "\n".join(hits))

    def test_reading_assignments_are_an_offer(self) -> None:
        for m in ("intake", "reconcile"):
            text = flat(SKILL / "modes" / f"{m}.md")
            with self.subTest(mode=m):
                self.assertIn("Offer a reading assignment", text)
                self.assertNotIn("Close with a reading assignment", text)

    def test_every_recommendation_still_carries_a_reason(self) -> None:
        text = flat(SKILL / "SKILL.md")
        self.assertIn("**(Recommended)** first, with one concrete reason", text)


class AltitudeColumn(unittest.TestCase):
    """§6 rows carry their altitude in a column; new writes it, arm and
    reconcile read it."""

    def test_new_arm_and_reconcile_name_the_column(self) -> None:
        for m in ("new", "arm", "reconcile"):
            with self.subTest(mode=m):
                self.assertIn("`Altitude` column", flat(SKILL / "modes" / f"{m}.md"))

    def test_new_lists_the_five_values(self) -> None:
        text = flat(SKILL / "modes" / "new.md")
        for v in ("`data`", "`response`", "`perception`", "`judgement`", "`sibling`"):
            self.assertIn(v, text)


class Interview(unittest.TestCase):
    def test_new_asks_for_every_part_of_the_human_half_and_the_owner(self) -> None:
        text = flat(SKILL / "modes" / "new.md")
        for phrase in (
            "what is true after this ships",
            "why do we need it",
            "what must always / never be true",
            "how will we know",
            "walk me through one concrete example",
            "git config user.name",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class Links(unittest.TestCase):
    def test_relative_links_resolve(self) -> None:
        files = [SKILL / "SKILL.md", *(SKILL / "modes" / f"{m}.md" for m in MODES)]
        files += [SKILL / "references" / r for r in REFERENCES_BUDGETED]
        broken = []
        for f in files:
            for match in sorted(set(m.group(0) for m in REL_LINK.finditer(f.read_text(encoding="utf-8")))):
                # a path with a trailing sentence punctuation is still the same target
                candidate = match.rstrip(".,;:)")
                if not (SKILL / candidate).exists():
                    broken.append(f"{f.relative_to(SKILL)} -> {candidate}")
        self.assertEqual(broken, [], "relative links that do not resolve:\n" + "\n".join(broken))

    def test_router_names_every_mode_file(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for m in MODES:
            self.assertIn(f"modes/{m}.md", text, f"SKILL.md does not route to modes/{m}.md")


class Sanitised(unittest.TestCase):
    """Nothing project-specific may appear anywhere under skills/promise/ —
    architecture.md included, now that its §6 example is the neutral example
    config verbatim. config.md and the example config show illustrative
    commands only."""

    def _files(self):
        for p in SKILL.rglob("*"):
            if p.suffix in {".md", ".py", ".json"}:
                yield p

    def test_no_project_names(self) -> None:
        hits = []
        for p in self._files():
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if LEAK_WORDS.search(line):
                    hits.append(f"{p.relative_to(SKILL)}:{i}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "project-specific names leaked:\n" + "\n".join(hits))

    def test_no_real_row_ids_or_dates(self) -> None:
        hits = []
        for p in self._files():
            if p.suffix == ".json":
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if ROW_ID.search(line) and "rowIdPattern" not in line and "C<n>" not in line:
                    hits.append(f"{p.relative_to(SKILL)}:{i}: row id: {line.strip()[:100]}")
                if YEAR.search(line) and "YYYY" not in line:
                    hits.append(f"{p.relative_to(SKILL)}:{i}: date: {line.strip()[:100]}")
        self.assertEqual(hits, [], "real row ids or dates leaked:\n" + "\n".join(hits))


    def test_no_history_references(self) -> None:
        """Reference docs state reasons, never lineage or past incidents. A future reader
        needs to know why a choice was made, not what went wrong somewhere else once."""
        hits = []
        for p in SKILL.rglob("*"):
            if p.suffix not in {".md", ".py"}:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if HISTORY.search(line):
                    hits.append(f"{p.relative_to(SKILL)}:{i}: {line.strip()[:100]}")
        self.assertEqual(hits, [], "history references in reference docs:\n" + "\n".join(hits))


class Templates(unittest.TestCase):
    def test_example_config_is_valid_json_with_known_keys(self) -> None:
        data = json.loads((SKILL / "templates" / "promise.config.example.json").read_text(encoding="utf-8"))
        keys = {k for k in data if not k.startswith("$")}
        self.assertTrue({"docsHome", "commands", "map"} <= keys, f"example config keys: {sorted(keys)}")
        self.assertIn("lanes", data["map"])
        self.assertIn("recipe", data["map"])

    def test_template_passes_the_lint(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "lint_outcome.py"), "--template", str(SKILL / "templates" / "outcome-doc.md")],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, f"template has lint findings:\n{proc.stdout}{proc.stderr}")

    def test_framework_does_not_embed_the_template(self) -> None:
        """templates/outcome-doc.md is the one home of the skeleton; a fenced copy
        in the framework would be a second home that drifts."""
        text = (SKILL / "outcome-framework.md").read_text(encoding="utf-8")
        self.assertNotIn("\n```markdown\n# <Capability>", text)
        self.assertNotIn("# <Capability>", text, "the framework must point at templates/outcome-doc.md, not copy it")
        self.assertIn("templates/outcome-doc.md", text)

    def test_template_rows_extract(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "outcome_rows.py"), str(SKILL / "templates" / "outcome-doc.md"), "--json"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertGreaterEqual(len(data["rows"]), 1)
        self.assertGreaterEqual(len(data["rules"]), 1)
        self.assertTrue(all(r["tags"] for r in data["rules"]), "every template rule carries a tag")


    def test_claude_md_section_template(self) -> None:
        text = (SKILL / "templates" / "claude-md-section.md").read_text(encoding="utf-8")
        body = text.strip().splitlines()
        self.assertTrue(body[0].startswith("<!-- promise:begin"), "first line must be the begin marker")
        self.assertEqual(body[-1].strip(), "<!-- promise:end -->", "last line must be the end marker")
        self.assertLessEqual(len(body), 20, f"the CLAUDE.md block is {len(body)} lines; budget 20")
        for ph in ("{docsHome}", "{configPath}", "{frameworkPath}"):
            self.assertIn(ph, text, f"template lacks placeholder {ph}")
        self.assertIn("/promise", text)


class ArchitectureIsExact(unittest.TestCase):
    """architecture.md calls its interfaces exact; two of its claims can be
    checked byte for byte."""

    def test_section_6_fence_is_the_example_config_verbatim(self) -> None:
        arch = (SKILL / "references" / "architecture.md").read_text(encoding="utf-8")
        section = arch.split("## 6. Config contract", 1)[1].split("\n## 7.", 1)[0]
        fence = re.search(r"```json\n(.*?)```", section, re.S).group(1)
        example = (SKILL / "templates" / "promise.config.example.json").read_text(encoding="utf-8")
        self.assertEqual(fence, example, "architecture.md §6 must show the example config verbatim")

    def test_section_3_tree_names_every_script_and_test_file(self) -> None:
        arch = (SKILL / "references" / "architecture.md").read_text(encoding="utf-8")
        tree = arch.split("## 3. File tree", 1)[1].split("\n## 4.", 1)[0]
        names = [p.name for p in (SKILL / "scripts").glob("*.py")]
        names += [p.name for p in HERE.glob("test_*.py")]
        missing = [n for n in names if n not in tree]
        self.assertEqual(missing, [], "architecture.md §3 tree is missing: " + ", ".join(missing))


class FrameworkSections(unittest.TestCase):
    SCRIPT = SKILL / "scripts" / "framework_section.py"

    def run_loader(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.SCRIPT), *args], capture_output=True, text=True, encoding="utf-8")

    def test_every_section_a_mode_header_names_exists(self) -> None:
        listed = self.run_loader("--list")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        names = {line[:45].strip().lower() for line in listed.stdout.splitlines()[1:]}
        for m in MODES:
            header = SKILL.joinpath("modes", f"{m}.md").read_text(encoding="utf-8").splitlines()[0]
            for sec in re.findall(r"§ ([A-Za-z][^·\n]*)", header):
                self.assertIn(sec.strip().lower(), names, f"modes/{m}.md names framework section {sec!r}, which does not exist")

    def test_named_sections_print_and_ignore_fenced_headings(self) -> None:
        out = self.run_loader("The contract", "Lifecycle")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("## The contract", out.stdout)
        self.assertIn("## Lifecycle", out.stdout)
        self.assertNotIn("## 0. TLDR", out.stdout, "headings inside the template's code fence are not sections")

    def test_unknown_or_ambiguous_name_exits_2(self) -> None:
        self.assertEqual(self.run_loader("No such section").returncode, 2)
        self.assertEqual(self.run_loader("The").returncode, 2)


if __name__ == "__main__":
    unittest.main()
