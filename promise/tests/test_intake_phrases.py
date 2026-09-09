"""The three intake phrasings from the router's dispatch table resolve to `intake`.

A person who says what they want in plain words must land on the right mode; these
are the table's own examples, so each is a regression test.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ORIENT = Path(__file__).resolve().parent.parent / "skills" / "promise" / "scripts" / "orient.py"

PHRASES = [
    "what does this map to",
    "turn this into scenarios / gherkins",
    "which capability covers muting a room",
    "add this as a scenario to the muted rooms row",
]


class IntakePhrases(unittest.TestCase):
    def test_table_phrases_suggest_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for phrase in PHRASES:
                proc = subprocess.run(
                    [sys.executable, str(ORIENT), "--cwd", tmp, "--input", phrase],
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                data = json.loads(proc.stdout)
                self.assertEqual(data["suggestedMode"], "intake", f"{phrase!r} -> {data['suggestedMode']} {data['signals']}")


class InputFile(unittest.TestCase):
    """A message with quotes and apostrophes never passes through a shell: it is read from a
    file or stdin, and the mode hint still comes out right."""

    MESSAGE = 'feedback: "context and citations should be added to the task properties"; it doesn\'t read inline'

    def test_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "msg.txt"
            path.write_text(self.MESSAGE, encoding="utf-8")
            proc = subprocess.run([sys.executable, str(ORIENT), "--cwd", tmp, "--input-file", str(path)],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["suggestedMode"], "intake", data["signals"])

    def test_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, str(ORIENT), "--cwd", tmp, "--input-file", "-"],
                                  input=self.MESSAGE, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["suggestedMode"], "intake")

    def test_missing_file_exits_2(self) -> None:
        proc = subprocess.run([sys.executable, str(ORIENT), "--input-file", "/nonexistent/msg.txt"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
