"""Tests for scripts/start_map.py and the starter map it installs.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

The starter map is what `/promise` recommends a project starts once its first
outcome doc is agreed. These tests hold three promises: it installs into an
adopted project and the rest of the skill sees a usable map straight after;
it never replaces a map a project already has, or writes anything when it
refuses; and the reader the minimap example runs is the same file the
starter ships, so the example cannot drift from what a project receives.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

TESTS_DIR = Path(__file__).resolve().parent
PROMISE_DIR = TESTS_DIR.parent
SKILL_DIR = PROMISE_DIR / "skills" / "promise"
SCRIPTS_DIR = SKILL_DIR / "scripts"
START_MAP = SCRIPTS_DIR / "start_map.py"
ADOPT = SCRIPTS_DIR / "adopt.py"
ORIENT = SCRIPTS_DIR / "orient.py"
TEMPLATE_DIR = SKILL_DIR / "templates" / "starter-map"
MINIMAP_READER = PROMISE_DIR / "examples" / "minimap" / "capability_find.py"


def run(script: Path, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    }


class StartMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / "CLAUDE.md").write_text("# project\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def adopt(self) -> None:
        proc = run(ADOPT, "--cwd", str(self.project), "--docs-home", "docs/designs")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def config(self) -> dict:
        return json.loads((self.project / ".claude" / "promise.config.json").read_text(encoding="utf-8"))

    def test_refuses_without_a_config_and_writes_nothing(self) -> None:
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("run adopt.py first", proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["changed"], False)
        self.assertEqual(snapshot(self.project), before)

    def test_dry_run_writes_nothing_and_shows_the_config_diff(self) -> None:
        self.adopt()
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(snapshot(self.project), before)
        self.assertIn('+    "recipe": "docs/capabilities/recipe.md",', proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["filesWritten"], [])
        self.assertEqual(result["changed"], False)

    def test_install_gives_a_usable_map_the_skill_can_run(self) -> None:
        self.adopt()
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(
            result["filesWritten"],
            ["docs/capabilities/map.json", "docs/capabilities/capability_find.py", "docs/capabilities/recipe.md"],
        )

        config = self.config()
        self.assertEqual(config["map"]["recipe"], "docs/capabilities/recipe.md")
        self.assertNotIn("$comment", config, "adopt's 'map is not configured yet' note must go")

        orientation = json.loads(run(ORIENT, "--cwd", str(self.project)).stdout)
        self.assertTrue(orientation["mapUsable"])

        reader = self.project / "docs" / "capabilities" / "capability_find.py"
        self.assertEqual(run(reader, "--next-id").stdout.strip(), "CAP-1")
        check = run(reader, "--check")
        self.assertEqual(check.returncode, 0, check.stderr)

        recipe = (self.project / "docs" / "capabilities" / "recipe.md").read_text(encoding="utf-8")
        self.assertNotIn("{dir}", recipe)
        self.assertIn("python3 docs/capabilities/capability_find.py --check", recipe)

    def test_doc_citations_resolve_from_the_project_root(self) -> None:
        """A row's doc is its project-relative path, although the map sits
        two folders down: docRoot carries the difference."""
        self.adopt()
        self.assertEqual(run(START_MAP, "--cwd", str(self.project)).returncode, 0)
        doc = self.project / "docs" / "designs" / "mute.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "| #    | Given | When | Then | Altitude | Row |\n"
            "|------|-------|------|------|----------|-----|\n"
            "| AT-1 | Ana is in a channel | she mutes it | she gets no push | perception | CAP-1 |\n",
            encoding="utf-8",
        )
        map_path = self.project / "docs" / "capabilities" / "map.json"
        data = json.loads(map_path.read_text(encoding="utf-8"))
        self.assertEqual(data["docRoot"], "../..")
        data["rows"].append({
            "id": "CAP-1",
            "story": "A member mutes a channel.",
            "doc": "docs/designs/mute.md",
            "scenarios": [{"id": "CAP-1.1", "at": "AT-1", "given": "Ana is in a channel",
                           "when": "she mutes it", "then": "she gets no push", "altitude": "perception"}],
            "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [],
            "verdict": "not-built",
        })
        map_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        check = run(map_path.parent / "capability_find.py", "--check")
        self.assertEqual(check.returncode, 0, check.stderr)

        doc.write_text("no table here\n", encoding="utf-8")
        check = run(map_path.parent / "capability_find.py", "--check")
        self.assertEqual(check.returncode, 1)
        self.assertIn("has no §6 line citing it", check.stderr)

    def test_never_replaces_an_existing_map(self) -> None:
        self.adopt()
        config_path = self.project / ".claude" / "promise.config.json"
        config = self.config()
        config["map"] = {"recipe": "docs/testing/recipe.md"}
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        before = snapshot(self.project)
        proc = run(START_MAP, "--cwd", str(self.project))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("never replaced", proc.stderr)
        self.assertEqual(snapshot(self.project), before)

    def test_refuses_a_destination_that_holds_files_or_escapes(self) -> None:
        self.adopt()
        occupied = self.project / "docs" / "capabilities"
        occupied.mkdir(parents=True)
        (occupied / "notes.md").write_text("mine\n", encoding="utf-8")
        before = snapshot(self.project)
        for dest in ("docs/capabilities", "../elsewhere", ".", "has space"):
            with self.subTest(dest=dest):
                proc = run(START_MAP, "--cwd", str(self.project), "--dest", dest)
                self.assertEqual(proc.returncode, 2, proc.stdout)
                self.assertEqual(snapshot(self.project), before)

    def test_custom_destination_sets_every_path(self) -> None:
        self.adopt()
        proc = run(START_MAP, "--cwd", str(self.project), "--dest", "capabilities")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.config()["map"]["find"], "python3 capabilities/capability_find.py")
        data = json.loads((self.project / "capabilities" / "map.json").read_text(encoding="utf-8"))
        self.assertEqual(data["docRoot"], "..")


class StarterTemplateTests(unittest.TestCase):
    def test_minimap_runs_the_reader_the_starter_ships(self) -> None:
        self.assertEqual(
            MINIMAP_READER.read_bytes(),
            (TEMPLATE_DIR / "capability_find.py").read_bytes(),
            "examples/minimap/capability_find.py must be a byte-for-byte copy of "
            "templates/starter-map/capability_find.py; change the template, then copy it",
        )

    def test_template_placeholders_are_the_ones_start_map_fills(self) -> None:
        self.assertIn("{docRoot}", (TEMPLATE_DIR / "map.json").read_text(encoding="utf-8"))
        self.assertIn("{dir}", (TEMPLATE_DIR / "recipe.md").read_text(encoding="utf-8"))
        self.assertNotIn("{dir}", (TEMPLATE_DIR / "capability_find.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
