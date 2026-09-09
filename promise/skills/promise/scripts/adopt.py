#!/usr/bin/env python3
"""Adopt the promise skill into a project: config file + CLAUDE.md section.

    python3 adopt.py --cwd /path/to/project
    python3 adopt.py --cwd /path/to/project --dry-run
    python3 adopt.py --docs-home docs/rfcs --no-config

A project is "adopted" once it has a `.claude/promise.config.json` and its
CLAUDE.md carries the promise section (references/architecture.md SS13), so
every person and agent working there is routed to `/promise` instead of
writing a design, plan or spec doc by hand.

Never overwrites an existing config. Idempotent: running it again with the
same inputs changes no bytes and reports "changed": false. A hand-edited
interior of the managed CLAUDE.md block is restored to the rendered form;
content outside the ``<!-- promise:begin`` / ``<!-- promise:end -->``
markers is left untouched. ``--dry-run`` writes nothing and prints a
unified diff to stderr; the JSON result is always the only line on stdout.
Exit 0 on success or no-op, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

BEGIN_PREFIX = "<!-- promise:begin"
END_MARKER = "<!-- promise:end -->"
TEMPLATE_NAME = "claude-md-section.md"
UNKNOWN_DOCS_HOME_TEXT = "the project's docs home"


def render_section(docs_home: Optional[str], config_path: str, framework_path: str, skill_dir: str) -> str:
    """Render templates/claude-md-section.md with {docsHome}/{configPath}/{frameworkPath}.

    Each placeholder is substituted with ``str.replace``, one at a time,
    rather than ``str.format`` — the template's own prose may contain
    other ``{``/``}`` characters that a format-string parse would choke on.
    ``config_path`` and ``framework_path`` arrive already made portable by
    ``display_paths``: a CLAUDE.md is committed and shared, so it must never
    carry one machine's absolute paths.
    """
    template_path = os.path.join(skill_dir, "templates", TEMPLATE_NAME)
    text = orient.read_text_tolerant(template_path)
    text = text.replace("{docsHome}", docs_home if docs_home else UNKNOWN_DOCS_HOME_TEXT)
    text = text.replace("{configPath}", config_path)
    text = text.replace("{frameworkPath}", framework_path)
    return text.rstrip("\n") + "\n"


def display_paths(cwd: str, config_path: str, orientation: Dict[str, Any]) -> Tuple[str, str]:
    """Project-relative config path, and a framework reference that is true on every machine."""
    config_display = os.path.relpath(config_path, cwd).replace(os.sep, "/")
    fw = orientation.get("frameworkPath")
    if orientation.get("frameworkSource") == "project" and fw:
        framework_display = os.path.relpath(fw, cwd).replace(os.sep, "/")
    else:
        framework_display = "the copy bundled with the promise skill"
    return config_display, framework_display


def build_config(effective_docs_home: Optional[str], commands: Dict[str, Any]) -> Dict[str, Any]:
    config: Dict[str, Any] = {"$schema": "promise.config/v1"}
    if effective_docs_home:
        config["docsHome"] = effective_docs_home
    command_fields = {
        k: v for k, v in commands.items() if k in ("typeCheck", "test", "lint") and v
    }
    if command_fields:
        config["commands"] = command_fields
    config["map"] = None
    config["$comment"] = (
        "map is not configured yet. See references/config.md for the shape "
        "(recipe, index, find/row/nextId commands, lanes, checks) and fill "
        "it in once this project has a capability map."
    )
    return config


def apply_claude_md(existing_text: Optional[str], rendered_section: str) -> str:
    """Insert or replace the managed block; content outside it is untouched."""
    section_text = rendered_section.rstrip("\n")
    if not existing_text:
        return section_text + "\n"

    lines = existing_text.splitlines(keepends=True)
    begin_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\r\n")
        if begin_idx is None and stripped.lstrip().startswith(BEGIN_PREFIX):
            begin_idx = i
            continue
        if begin_idx is not None and end_idx is None and stripped == END_MARKER:
            end_idx = i
            break

    if begin_idx is not None and end_idx is not None:
        before = "".join(lines[:begin_idx])
        after = "".join(lines[end_idx + 1 :])
        return before + section_text + "\n" + after

    # No existing block: append after exactly one blank line.
    return existing_text.rstrip("\n") + "\n\n" + section_text + "\n"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adopt.py",
        description="Write .claude/promise.config.json and insert the CLAUDE.md pointer section.",
    )
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; print a unified diff to stderr")
    parser.add_argument("--docs-home", default=None, help="docsHome to record in a freshly written config")
    parser.add_argument("--no-config", action="store_true", help="skip writing the config file")
    parser.add_argument("--no-claude-md", action="store_true", help="skip the CLAUDE.md section")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"adopt.py: no such directory: {cwd}", file=sys.stderr)
        return 2

    skill_dir = orient.get_skill_dir()
    orientation = orient.build_orientation(None, cwd)

    effective_docs_home = args.docs_home or (
        orientation["docsHome"] if orientation["docsHomeSource"] != "none" else None
    )

    config_path = os.path.join(cwd, ".claude", "promise.config.json")
    config_written = False
    config_diff = ""

    if not args.no_config:
        if os.path.isfile(config_path):
            print(f"adopt.py: config already exists at {config_path}; not overwriting", file=sys.stderr)
        else:
            new_config = build_config(effective_docs_home, orientation["commands"])
            new_text = json.dumps(new_config, indent=2, ensure_ascii=False) + "\n"
            if args.dry_run:
                rel = os.path.relpath(config_path, cwd)
                config_diff = "".join(
                    difflib.unified_diff([], new_text.splitlines(keepends=True), fromfile=rel, tofile=rel)
                )
            else:
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new_text)
                config_written = True

    claude_md_written = False
    claude_md_changed = False
    claude_md_diff = ""
    claude_md_path = orientation["claudeMd"]["path"] or os.path.join(cwd, "CLAUDE.md")

    if not args.no_claude_md:
        config_display, framework_display = display_paths(cwd, config_path, orientation)
        rendered = render_section(effective_docs_home, config_display, framework_display, skill_dir)
        existing_text = orient.read_text_tolerant(claude_md_path) if os.path.isfile(claude_md_path) else None
        new_text = apply_claude_md(existing_text, rendered)
        claude_md_changed = existing_text != new_text
        if claude_md_changed:
            if args.dry_run:
                rel = os.path.relpath(claude_md_path, cwd)
                claude_md_diff = "".join(
                    difflib.unified_diff(
                        (existing_text or "").splitlines(keepends=True),
                        new_text.splitlines(keepends=True),
                        fromfile=rel,
                        tofile=rel,
                    )
                )
            else:
                with open(claude_md_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(new_text)
                claude_md_written = True

    if args.dry_run:
        would_write_config = (not args.no_config) and (not os.path.isfile(config_path))
        changed = bool(would_write_config or claude_md_changed)
    else:
        changed = bool(config_written or claude_md_written)

    diff_text = config_diff + claude_md_diff
    if args.dry_run and diff_text:
        sys.stderr.write(diff_text)

    result = {
        "configWritten": config_written,
        "configPath": config_path,
        "claudeMdWritten": claude_md_written,
        "claudeMdPath": claude_md_path,
        "changed": changed,
        "dryRun": args.dry_run,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
