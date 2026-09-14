"""Packaging parity: the pre-install surfaces must agree with the plugin.

A claim on a pre-install surface must never be contradicted by a file inside the
plugin. Locked here: the marketplace entry's description is byte-identical to
plugin.json's; every count of modes on a packaging surface is the number of files in
modes/; plugin.json's version matches the top CHANGELOG entry; and the removed
`outcome` plugin is neither listed nor installed anywhere.
"""
import json
import pathlib
import re
import unittest

PROMISE = pathlib.Path(__file__).resolve().parents[1]
ROOT = PROMISE.parent
MODES_DIR = PROMISE / "skills" / "promise" / "modes"
# "one mode" and "two modes" are ordinary prose ("asks only when two modes are
# plausible"); a count claim about the plugin starts at three.
NUMBER_WORDS = {
    "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
SURFACES = [
    ROOT / "README.md",
    ROOT / ".claude-plugin" / "marketplace.json",
    PROMISE / "README.md",
    PROMISE / "CHANGELOG.md",
    PROMISE / ".claude-plugin" / "plugin.json",
    PROMISE / "skills" / "promise" / "SKILL.md",
    PROMISE / "skills" / "promise" / "references" / "architecture.md",
]


def read(path):
    return path.read_text(encoding="utf-8")


class PackagingParity(unittest.TestCase):
    def test_marketplace_description_is_plugin_description(self):
        plugin = json.loads(read(PROMISE / ".claude-plugin" / "plugin.json"))
        market = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))
        entries = [p for p in market["plugins"] if p["name"] == "promise"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["description"], plugin["description"])

    def test_mode_count_words_match_modes_dir(self):
        n = len(list(MODES_DIR.glob("*.md")))
        self.assertGreater(n, 0)
        pattern = re.compile(r"\b(%s)\s+modes?\b" % "|".join(NUMBER_WORDS), re.IGNORECASE)
        for path in SURFACES:
            for m in pattern.finditer(read(path)):
                word = m.group(1).lower()
                self.assertEqual(
                    NUMBER_WORDS[word], n,
                    "%s says '%s' but modes/ holds %d files" % (path.relative_to(ROOT), m.group(0), n),
                )

    def test_plugin_version_is_top_changelog_entry(self):
        plugin = json.loads(read(PROMISE / ".claude-plugin" / "plugin.json"))
        m = re.search(r"(?m)^## (\d+\.\d+\.\d+)\s*$", read(PROMISE / "CHANGELOG.md"))
        self.assertIsNotNone(m)
        self.assertEqual(plugin["version"], m.group(1))

    def test_outcome_plugin_is_gone(self):
        self.assertFalse((ROOT / "outcome").exists())
        market = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))
        self.assertNotIn("outcome", [p["name"] for p in market["plugins"]])
        self.assertNotIn("outcome@content-skills", read(ROOT / "README.md"))
        self.assertNotIn("outcome@content-skills", read(PROMISE / "README.md"))

    def test_agreed_is_not_listed_as_a_mode(self):
        plugin = json.loads(read(PROMISE / ".claude-plugin" / "plugin.json"))
        self.assertNotIn("`agreed` files", plugin["description"])


if __name__ == "__main__":
    unittest.main()
