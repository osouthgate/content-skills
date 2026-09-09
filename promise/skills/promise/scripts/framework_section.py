#!/usr/bin/env python3
"""Print named sections of the Outcome Framework, so a mode reads only what it needs.

    python3 framework_section.py "The contract" "Section rules"
    python3 framework_section.py --list
    python3 framework_section.py --framework docs/how-to/outcome-framework.md "Lifecycle"

A section is a top-level `## ` heading of the framework; headings inside fenced code
blocks (the template illustration) are not sections. Names match case-insensitively,
by exact text or by unambiguous prefix. The framework path resolves the same way the
skill resolves it: `--framework`, else `frameworkPath` in `.claude/promise.config.json`
(or `promise.config.json`) under `--cwd` when that file exists, else the copy bundled
beside this script's directory.

Exit 0 on success; 2 when a name matches no section or more than one (the available
names are printed). Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent


def resolve_framework(cwd: Path, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for rel in (".claude/promise.config.json", "promise.config.json"):
        cfg = cwd / rel
        if cfg.is_file():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError):
                break
            fp = data.get("frameworkPath") if isinstance(data, dict) else None
            if isinstance(fp, str) and (cwd / fp).is_file():
                return (cwd / fp).resolve()
            break
    return SKILL_DIR / "outcome-framework.md"


def split_sections(text: str) -> List[Tuple[str, int, int, List[str]]]:
    """Return (name, start_line, end_line, lines) per top-level section, 1-based inclusive."""
    lines = text.splitlines()
    sections: List[Tuple[str, int, int, List[str]]] = []
    in_fence = False
    current: Optional[Tuple[str, int]] = None
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if not in_fence and line.startswith("## "):
            if current is not None:
                sections.append((current[0], current[1], i - 1, lines[current[1] - 1 : i - 1]))
            current = (line[3:].strip(), i)
    if current is not None:
        sections.append((current[0], current[1], len(lines), lines[current[1] - 1 :]))
    return sections


def find(name: str, sections: List[Tuple[str, int, int, List[str]]]):
    key = name.strip().lower().lstrip("§").strip()
    exact = [s for s in sections if s[0].lower() == key]
    if len(exact) == 1:
        return exact[0], None
    prefix = [s for s in sections if s[0].lower().startswith(key)]
    if len(prefix) == 1:
        return prefix[0], None
    if not prefix:
        return None, f"no section named {name!r}"
    return None, f"{name!r} is ambiguous: " + ", ".join(repr(s[0]) for s in prefix)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="section names, e.g. 'The contract' 'Lifecycle'")
    ap.add_argument("--cwd", default=".", help="project root used to find a config (default: .)")
    ap.add_argument("--framework", help="explicit path to the framework file")
    ap.add_argument("--list", action="store_true", help="list the sections with line ranges and sizes")
    args = ap.parse_args(argv)

    path = resolve_framework(Path(args.cwd).resolve(), args.framework)
    if not path.is_file():
        print(f"framework not found: {path}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    sections = split_sections(text)

    if args.list or not args.names:
        print(f"# {path}")
        for name, start, end, body in sections:
            approx = sum(len(l) + 1 for l in body) // 4
            print(f"{name:45s} lines {start:4d}-{end:4d}  ~{approx:5d} tokens")
        return 0 if args.list else 2

    out: List[str] = []
    for name in args.names:
        hit, err = find(name, sections)
        if err:
            print(err, file=sys.stderr)
            print("available: " + ", ".join(repr(s[0]) for s in sections), file=sys.stderr)
            return 2
        out.append("\n".join(hit[3]).rstrip() + "\n")
    sys.stdout.write("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
