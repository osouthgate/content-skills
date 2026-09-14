#!/usr/bin/env python3
"""Print named sections of the Outcome Framework, so a mode reads only what it needs.

    python3 framework_section.py "The contract" "Section rules"
    python3 framework_section.py --list
    python3 framework_section.py --framework docs/how-to/outcome-framework.md "Lifecycle"

A section is a top-level `## ` heading of the framework; headings inside fenced code
blocks are not sections. Names match case-insensitively, by exact text or by
unambiguous prefix. The framework path comes from orient.py's resolver — the one
Phase 0 uses — so the two can never disagree: `--framework`, else `frameworkPath`
in `.claude/promise.config.json` (or `promise.config.json`) under `--cwd` when that
path stays inside the project and the file exists, else the copy bundled beside this
script's directory. A configured path that is rejected (it escapes the project, or
is not there) is reported on stderr and the bundled copy is used, exactly as orient
reports it.

Exit 0 on success; 2 with a message on stderr when no section name and no `--list`
is given, when a name matches no section or more than one (the available names are
printed), when `--cwd` is not a directory, or when the framework file cannot be read
as UTF-8. Standard library only.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

SKILL_DIR = Path(__file__).resolve().parent.parent


def resolve_framework(cwd: Path, explicit: Optional[str]) -> Tuple[Path, List[str]]:
    """(framework path, warnings) — `--framework` wins outright; otherwise
    orient.py resolves the config's frameworkPath on the same terms Phase 0 does."""
    if explicit:
        return Path(explicit).expanduser().resolve(), []
    warnings: List[str] = []
    config, _config_path, config_warnings = orient.load_config(str(cwd))
    path, _source = orient.resolve_framework_path(str(cwd), config, str(SKILL_DIR), warnings)
    relevant = [w for w in config_warnings + warnings if "frameworkPath" in w]
    return Path(path), relevant


def split_sections(text: str) -> List[Tuple[str, int, int, List[str]]]:
    """Return (name, start_line, end_line, lines) per top-level section, 1-based inclusive."""
    lines = text.splitlines()
    scan = orient.unfenced(lines)
    sections: List[Tuple[str, int, int, List[str]]] = []
    current: Optional[Tuple[str, int]] = None
    for i, line in enumerate(scan, 1):
        if line.startswith("## "):
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
    ap = argparse.ArgumentParser(prog="framework_section.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("names", nargs="*", help="section names, e.g. 'The contract' 'Lifecycle'")
    ap.add_argument("--cwd", default=".", help="project root used to find a config (default: .)")
    ap.add_argument("--framework", help="explicit path to the framework file")
    ap.add_argument("--list", action="store_true", help="list the sections with line ranges and sizes")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if not args.list and not args.names:
        ap.print_usage(sys.stderr)
        print("framework_section.py: name at least one section, or pass --list", file=sys.stderr)
        return 2

    if not os.path.isdir(args.cwd):
        print(f"framework_section.py: no such directory: {args.cwd}", file=sys.stderr)
        return 2

    path, warnings = resolve_framework(Path(args.cwd).resolve(), args.framework)
    for warning in warnings:
        print(f"framework_section.py: {warning}", file=sys.stderr)
    if not path.is_file():
        print(f"framework not found: {path}", file=sys.stderr)
        return 2
    try:
        text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        print(f"framework_section.py: {path} is not UTF-8: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"framework_section.py: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    sections = split_sections(text)

    if args.list:
        print(f"# {path}")
        for name, start, end, body in sections:
            approx = sum(len(l) + 1 for l in body) // 4
            print(f"{name:45s} lines {start:4d}-{end:4d}  ~{approx:5d} tokens")
        return 0

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
