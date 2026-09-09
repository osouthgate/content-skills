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
    """Nothing project-specific may appear outside architecture.md (which records the
    reference project's measurements) and config.md / the example config (which show
    illustrative commands)."""

    def _files(self):
        for p in SKILL.rglob("*"):
            if p.suffix in {".md", ".py", ".json"} and p.name != "architecture.md":
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
            [sys.executable, str(SKILL / "scripts" / "lint_outcome.py"), str(SKILL / "templates" / "outcome-doc.md")],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, f"template has lint findings:\n{proc.stdout}{proc.stderr}")

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
