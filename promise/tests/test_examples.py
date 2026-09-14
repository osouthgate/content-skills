"""Tests for the shipped examples under promise/examples/.

Run from the repo root:

    python3 -m unittest discover -s promise/tests -v

The examples are the plugin's own claims made concrete: an outcome doc that
is not a fixture, and a capability map small enough to watch the bridge on.
An example that rots is worse than none, so every script the examples'
README tells a reader to run is run here, as a real subprocess, against the
shipped files — never a copy with the interesting parts substituted. The
one substitution made is the interpreter name: the shipped config says
``python3`` because that is what a reader types; on a host with no
``python3`` on PATH the map commands are rewritten to ``sys.executable`` in
a temporary copy, and the test says so in its name.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
PROMISE_DIR = TESTS_DIR.parent
REPO_DIR = PROMISE_DIR.parent
SCRIPTS_DIR = PROMISE_DIR / "skills" / "promise" / "scripts"
EXAMPLES_DIR = PROMISE_DIR / "examples"
MINIMAP_DIR = EXAMPLES_DIR / "minimap"

LINT = SCRIPTS_DIR / "lint_outcome.py"
ORIENT = SCRIPTS_DIR / "orient.py"
ADAPTER = SCRIPTS_DIR / "adapter.py"
BRIDGE = SCRIPTS_DIR / "bridge_validate.py"
OUTCOME_ROWS = SCRIPTS_DIR / "outcome_rows.py"

DRAFT_DOC = EXAMPLES_DIR / "channel-muting.md"
BRIDGED_DOC = MINIMAP_DIR / "docs" / "designs" / "channel-muting.md"
TRANSCRIPT = EXAMPLES_DIR / "transcript.md"
MAP_JSON = MINIMAP_DIR / "map.json"
CAPABILITY_FIND = MINIMAP_DIR / "capability_find.py"
MINIMAP_CONFIG = MINIMAP_DIR / "promise.config.json"
WORKFLOW = REPO_DIR / ".github" / "workflows" / "tests.yml"

OUTCOME_DOCS = (DRAFT_DOC, BRIDGED_DOC)

# The bridge's edits to the draft, and nothing else: Status, the Row header
# and separator cells, one Row cell per data row, and the snapshot line.
BRIDGE_ROW_IDS = {"AT-1": "CAP-1", "AT-2": "CAP-1", "AT-3": "CAP-2"}
SNAPSHOT_LINE = "Snapshot taken at `agreed` on 2026-01-01; the map is the source of these scenarios from here on."


def run(script: Path, *args: str, cwd: Optional[Path] = None, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(cwd) if cwd else None,
        input=stdin,
    )


def bridge_the_draft(text: str) -> str:
    """The draft example with exactly the edits arm's bridge step makes."""
    out: List[str] = []
    for line in text.splitlines():
        if line == "Status: draft":
            line = "Status: agreed"
        elif line.startswith("| #    | Given | When | Then | Altitude |"):
            line = line + " Row |"
        elif line.startswith("|------|-------|------|------|----------|"):
            line = line + "-----|"
        else:
            m = re.match(r"^\| (AT-\d+) \|", line)
            if m and m.group(1) in BRIDGE_ROW_IDS:
                line = line + f" {BRIDGE_ROW_IDS[m.group(1)]} |"
        out.append(line)
        if line.startswith("| AT-3 |"):
            out.append("")
            out.append(SNAPSHOT_LINE)
    return "\n".join(out) + "\n"


class _MinimapProject:
    """The shipped minimap directory, or — only when ``python3`` is not on
    PATH — a temporary copy whose map commands name this interpreter."""

    _tmp: Optional[tempfile.TemporaryDirectory] = None
    path: Path = MINIMAP_DIR
    substituted: bool = False

    @classmethod
    def get(cls) -> Path:
        if cls.substituted or shutil.which("python3"):
            return cls.path
        cls._tmp = tempfile.TemporaryDirectory()
        copy = Path(cls._tmp.name) / "minimap"
        shutil.copytree(MINIMAP_DIR, copy)
        config_path = copy / "promise.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        exe = json.dumps(sys.executable)[1:-1]
        for key in ("find", "row", "nextId"):
            config["map"][key] = config["map"][key].replace("python3 ", f'"{exe}" ', 1)
        config["map"]["checks"] = [c.replace("python3 ", f'"{exe}" ', 1) for c in config["map"]["checks"]]
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        cls.path = copy
        cls.substituted = True
        return cls.path


def minimap() -> Path:
    return _MinimapProject.get()


class FilesExistTests(unittest.TestCase):
    def test_every_example_file_is_shipped(self) -> None:
        for path in (DRAFT_DOC, TRANSCRIPT, BRIDGED_DOC, MAP_JSON, CAPABILITY_FIND, MINIMAP_CONFIG,
                     MINIMAP_DIR / "recipe.md", MINIMAP_DIR / "README.md"):
            self.assertTrue(path.is_file(), f"missing example file: {path}")

    def test_transcript_says_it_is_illustrative(self) -> None:
        text = TRANSCRIPT.read_text(encoding="utf-8")
        self.assertIn("not a recording", text)
        for marker in ("Phase 0", "Reading this as **new**", "adopt", "render_outcome.py", "lint_outcome.py", "## 0. TLDR"):
            self.assertIn(marker, text, f"transcript lacks {marker!r}")

    def test_workflow_runs_the_suite_on_push_and_pull_request(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("ubuntu-latest", text)
        self.assertIn('python-version: "3.12"', text)
        self.assertIn("python3 -m unittest discover -s promise/tests -v", text)
        triggers = text.split("\non:", 1)[1].split("\njobs:", 1)[0]
        self.assertIn("push:", triggers, "the workflow does not run on push")
        self.assertIn("pull_request:", triggers, "the workflow does not run on pull_request")


class LintTests(unittest.TestCase):
    def test_example_docs_lint_clean(self) -> None:
        for doc in OUTCOME_DOCS:
            with self.subTest(doc=doc.relative_to(PROMISE_DIR)):
                proc = run(LINT, "--json", str(doc))
                self.assertEqual(proc.returncode, 0, f"{doc.name}: {proc.stdout}{proc.stderr}")
                data = json.loads(proc.stdout)
                self.assertEqual(data["findings"], [], f"{doc.name} has lint findings:\n{proc.stdout}")

    def test_example_docs_lint_clean_under_strict(self) -> None:
        for doc in OUTCOME_DOCS:
            with self.subTest(doc=doc.relative_to(PROMISE_DIR)):
                proc = run(LINT, "--strict", str(doc))
                self.assertEqual(proc.returncode, 0, f"{doc.name}: {proc.stdout}{proc.stderr}")

    def test_draft_example_retags_the_per_member_rule(self) -> None:
        proc = run(OUTCOME_ROWS, str(DRAFT_DOC), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "draft")
        self.assertEqual([r["tags"] for r in data["rules"]], [["AT-1", "AT-2"], ["AT-3"]])
        self.assertEqual([r["id"] for r in data["rows"]], ["AT-1", "AT-2", "AT-3"])
        self.assertTrue(all(r["row"] is None for r in data["rows"]), "the draft carries no Row values")

    def test_draft_example_has_an_altitude_per_row(self) -> None:
        lines = DRAFT_DOC.read_text(encoding="utf-8").splitlines()
        header = next(l for l in lines if l.startswith("| #"))
        cells = [c.strip().lower() for c in header.strip("|").split("|")]
        self.assertIn("altitude", cells)
        idx = cells.index("altitude")
        allowed = {"data", "response", "perception", "judgement", "sibling"}
        for line in lines:
            if re.match(r"^\| AT-\d+ \|", line):
                value = [c.strip() for c in line.strip("|").split("|")][idx]
                self.assertIn(value, allowed, f"{line!r} has altitude {value!r}")

    def test_section_ten_owners_are_linked(self) -> None:
        text = DRAFT_DOC.read_text(encoding="utf-8")
        section_ten = text.split("## 10. Out of scope", 1)[1]
        self.assertGreaterEqual(len(re.findall(r"\[[^\]]+\]\([^)]+\.md\)", section_ten)), 2)

    def test_bridged_doc_is_the_draft_plus_the_bridge(self) -> None:
        expected = bridge_the_draft(DRAFT_DOC.read_text(encoding="utf-8"))
        self.assertEqual(BRIDGED_DOC.read_text(encoding="utf-8"), expected)


class OrientTests(unittest.TestCase):
    def test_orient_reports_a_usable_map(self) -> None:
        project = minimap()
        proc = run(ORIENT, "--cwd", str(project))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["mapUsable"], data["warnings"])
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertEqual(data["docsHomeSource"], "config")
        self.assertEqual(data["map"]["rowIdPattern"], r"^CAP-\d+$")
        self.assertEqual(set(data["map"]["lanes"]), {"data", "response", "perception", "judgement", "sibling"})
        self.assertEqual([d["path"] for d in data["existingDocs"]], ["docs/designs/channel-muting.md"])
        self.assertFalse(any(w.startswith("map incomplete") for w in data["warnings"]), data["warnings"])

    def test_config_declares_version_one(self) -> None:
        config = json.loads(MINIMAP_CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config.get("version"), 1)
        self.assertNotIn("$schema", config)
        self.assertEqual(config["map"]["recipe"], "recipe.md")
        self.assertTrue((MINIMAP_DIR / config["map"]["recipe"]).is_file())


class AdapterTests(unittest.TestCase):
    def adapter(self, *args: str) -> subprocess.CompletedProcess:
        return run(ADAPTER, "--cwd", str(minimap()), *args)

    def adapter_json(self, *args: str) -> Tuple[subprocess.CompletedProcess, dict]:
        proc = run(ADAPTER, "--cwd", str(minimap()), "--json", *args)
        return proc, (json.loads(proc.stdout) if proc.stdout.strip() else None)

    def test_show_lists_every_map_command_and_runs_nothing(self) -> None:
        proc = self.adapter("show")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        labels = [line.split(":", 1)[0] for line in proc.stdout.splitlines() if ":" in line]
        for label in ("map.find", "map.row", "map.nextId", "map.checks[0]"):
            self.assertIn(label, labels, proc.stdout)
        self.assertIn("capability_find.py", proc.stdout)

    def test_find_returns_ranked_rows(self) -> None:
        proc, result = self.adapter_json("find", "mute a channel")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["exit"], 0, result["stderr"])
        self.assertEqual(result["argv"][-1], "mute a channel", "the query travels as one argv element")
        rows = json.loads(result["stdout"])
        self.assertEqual(rows[0]["id"], "CAP-1")
        self.assertEqual({r["id"] for r in rows}, {"CAP-1", "CAP-2", "CAP-3"})
        scores = [r["score"] for r in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_find_with_no_hits_is_an_empty_array(self) -> None:
        proc, result = self.adapter_json("find", "zzzz qqqq")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(result["stdout"]), [])

    def test_find_query_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            query_path = Path(tmp) / "query.txt"
            query_path.write_text('the "quiet hours" mute\n', encoding="utf-8")
            proc, result = self.adapter_json("find", "--query-file", str(query_path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["argv"][-1], 'the "quiet hours" mute')
        self.assertEqual(json.loads(result["stdout"])[0]["id"], "CAP-1")

    def test_row_returns_the_row(self) -> None:
        proc, result = self.adapter_json("row", "CAP-1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        row = json.loads(result["stdout"])
        self.assertEqual(row["id"], "CAP-1")
        self.assertEqual([s["at"] for s in row["scenarios"]], ["AT-1", "AT-2"])
        self.assertEqual(row["verdict"], "not-built")

    def test_row_unknown_id_exits_2_from_the_map_command(self) -> None:
        proc, result = self.adapter_json("row", "CAP-9")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(result["exit"], 2, "capability_find.py exits 2 on an unknown id")
        self.assertIn("no such row", result["stderr"])

    def test_row_id_failing_the_pattern_is_refused_before_anything_runs(self) -> None:
        proc = self.adapter("--json", "row", "nope")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("rowIdPattern", proc.stderr)

    def test_next_id(self) -> None:
        proc, result = self.adapter_json("next-id")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(result["stdout"].strip(), "CAP-4")

    def test_checks_pass(self) -> None:
        proc, results = self.adapter_json("checks")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exit"], 0, results[0]["stderr"])
        self.assertIn("0 problems", results[0]["stdout"])


class CapabilityFindTests(unittest.TestCase):
    """capability_find.py on its own terms — the part a project supplies."""

    def test_check_finds_a_broken_verdict(self) -> None:
        data = json.loads(MAP_JSON.read_text(encoding="utf-8"))
        data["rows"][0]["verdict"] = "done"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "map.json"
            broken.write_text(json.dumps(data), encoding="utf-8")
            proc = run(CAPABILITY_FIND, "--map", str(broken), "--check")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("verdict 'done'", proc.stderr)

    def test_no_argument_is_a_usage_error(self) -> None:
        proc = run(CAPABILITY_FIND)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")

    def _check_with_extra_row(self, extra: dict) -> subprocess.CompletedProcess:
        """--check over a copy of the minimap whose map carries one more row."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "minimap"
            shutil.copytree(MINIMAP_DIR, project)
            map_path = project / "map.json"
            data = json.loads(map_path.read_text(encoding="utf-8"))
            data["rows"].append(extra)
            map_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return run(project / "capability_find.py", "--check")

    def _row(self, **overrides) -> dict:
        row = {
            "id": "CAP-4", "story": "A member sees a mute expire.", "doc": "docs/designs/channel-muting.md",
            "scenarios": [{"id": "CAP-4.1", "at": "AT-9", "given": "g", "when": "w", "then": "t", "altitude": "data"}],
            "tests": [], "e2eTests": [], "evalTests": [], "siblingTests": [], "verdict": "not-built",
        }
        row.update(overrides)
        return row

    def test_check_finds_a_row_whose_doc_does_not_cite_it(self) -> None:
        """recipe.md's step 5, map-to-doc direction: a row that names a doc
        no §6 line cites fails --check. bridge_validate.py reads only the
        doc-to-map direction, so this is the one place it is caught."""
        proc = self._check_with_extra_row(self._row())
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("CAP-4: doc docs/designs/channel-muting.md has no §6 line citing it", proc.stderr)
        self.assertIn("1 problems", proc.stdout)

    def test_check_accepts_a_row_filed_from_feedback_with_no_doc(self) -> None:
        proc = self._check_with_extra_row(self._row(doc=None))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_check_validates_parent_as_a_row_id(self) -> None:
        proc = self._check_with_extra_row(self._row(doc=None, parent="CAP-3"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        proc = self._check_with_extra_row(self._row(doc=None, parent="story 3"))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("parent 'story 3' is not a row id", proc.stderr)

    def test_malformed_row_id_exits_2(self) -> None:
        proc = run(CAPABILITY_FIND, "--row", "R1")
        self.assertEqual(proc.returncode, 2)

    def test_map_rows_match_the_bridged_doc(self) -> None:
        """The map's scenario Then text is the doc's Then text, verbatim, per recipe.md."""
        data = json.loads(MAP_JSON.read_text(encoding="utf-8"))
        proc = run(OUTCOME_ROWS, str(BRIDGED_DOC), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc_rows = {r["id"]: r for r in json.loads(proc.stdout)["rows"]}
        by_at: Dict[str, dict] = {}
        for row in data["rows"]:
            for scenario in row["scenarios"]:
                if scenario["at"]:
                    by_at[scenario["at"]] = dict(scenario, rowId=row["id"])
        self.assertEqual(set(by_at), set(doc_rows))
        for at, doc_row in doc_rows.items():
            self.assertEqual(by_at[at]["then"], doc_row["then"], at)
            self.assertEqual(by_at[at]["rowId"], doc_row["row"], at)


class BridgeValidateTests(unittest.TestCase):
    def bridge_json(self, doc: Path) -> Tuple[subprocess.CompletedProcess, dict]:
        proc = run(BRIDGE, str(doc), "--cwd", str(minimap()), "--json")
        return proc, (json.loads(proc.stdout) if proc.stdout.strip() else None)

    def assert_clean_bridge(self, proc: subprocess.CompletedProcess, data: dict) -> None:
        self.assertEqual(proc.returncode, 0, f"{proc.stdout}{proc.stderr}")
        self.assertTrue(data["bridged"])
        self.assertTrue(data["mapConfigured"])
        self.assertEqual(data["stats"]["errors"], 0, data["findings"])
        self.assertEqual(data["stats"]["rows"], 3)
        self.assertEqual(data["stats"]["mapped"], 3)
        self.assertEqual(data["stats"]["drifted"], 0, data["findings"])
        self.assertEqual([f["rule"] for f in data["findings"]], [])
        self.assertTrue(all(r["found"] and r["inSync"] for r in data["rows"]), data["rows"])

    def test_shipped_bridged_doc_validates_with_zero_errors(self) -> None:
        proc, data = self.bridge_json(BRIDGED_DOC)
        self.assert_clean_bridge(proc, data)

    def test_a_bridged_copy_of_the_draft_validates_with_zero_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "channel-muting.md"
            copy.write_text(bridge_the_draft(DRAFT_DOC.read_text(encoding="utf-8")), encoding="utf-8")
            proc, data = self.bridge_json(copy)
        self.assert_clean_bridge(proc, data)

    def test_human_output_summary_line(self) -> None:
        proc = run(BRIDGE, str(BRIDGED_DOC), "--cwd", str(minimap()))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip().splitlines()[-1], "bridge: 3 rows, 3 mapped, 0 drifted")

    def test_the_draft_itself_is_not_bridged(self) -> None:
        proc, data = self.bridge_json(DRAFT_DOC)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(data["bridged"])
        self.assertEqual([f["rule"] for f in data["findings"]], ["NOT_BRIDGED"])

    def test_a_map_edit_shows_up_as_drift(self) -> None:
        """The README's first demonstration: change a Then in the map and the
        doc's snapshot no longer matches — THEN_NOT_IN_MAP, the map as suspect."""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "minimap"
            shutil.copytree(minimap(), project)
            map_path = project / "map.json"
            data = json.loads(map_path.read_text(encoding="utf-8"))
            data["rows"][1]["scenarios"][0]["then"] = "Ben keeps getting pushes"
            map_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            proc = run(BRIDGE, str(project / "docs" / "designs" / "channel-muting.md"), "--cwd", str(project), "--json")
            result = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, "drift is a warning, not an error")
        self.assertEqual([f["rule"] for f in result["findings"]], ["THEN_NOT_IN_MAP"])
        self.assertEqual(result["stats"]["drifted"], 1)


if __name__ == "__main__":
    unittest.main()
