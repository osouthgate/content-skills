#!/usr/bin/env python3
"""Render a new outcome doc from the template, with the header fields filled in.

    python3 render_outcome.py --title "<Capability>" --owner "<name>" [--date YYYY-MM-DD] [--docs-home DIR] [--cwd DIR] [--dry-run] [--json]

Copies ``templates/outcome-doc.md`` — found relative to this script's own
directory, not the current working directory — and fills in exactly four
things: the H1 title, the owner in the header's ``Owner:`` line, the
owner in section 0's author line, and the date everywhere the template
spells it (the header's ``Last decision:`` and section 0's author line).
Every other placeholder in the template — the outcome line, each rule,
worked examples, section 9's own unrelated ``<name>`` in its owner
example — is left exactly as the template wrote it; the interview that
follows this script fills those in by hand.

The date defaults to today, in ISO form (``YYYY-MM-DD``). The
destination is ``<docsHome>/<slug>.md``, where the slug is the title
lower-cased, with every run of characters outside ``a-z0-9`` collapsed to
one hyphen and the result trimmed of leading and trailing hyphens.
``docsHome`` comes from ``--docs-home`` when given, else from
``orient.py``'s resolution for the project at ``--cwd``; when neither
names one, the script refuses rather than guessing where a document
should live.

The script never overwrites an existing file at the destination — it
refuses and names the path instead. ``--dry-run`` renders the text and
prints it to stdout without writing anything. ``--json`` prints one
object ``{"path", "written", "slug"}`` instead of the rendered text or a
confirmation line; combined with ``--dry-run`` it reports
``"written": false`` and still writes nothing. The file itself, when
written, uses ``\\n`` line endings and UTF-8, regardless of the platform
this runs on.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

TEMPLATE_RELATIVE_PATH = os.path.join("..", "templates", "outcome-doc.md")

_SLUG_COLLAPSE_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Lower-case ``title``; collapse every run of non ``a-z0-9`` characters to one
    hyphen; trim leading and trailing hyphens.

    ASCII letters and digits only survive as themselves — an accented or
    non-Latin letter is collapsed like any other non-alphanumeric
    character — so the result is always a safe, portable filename
    fragment regardless of what script the title was typed in.
    """
    lowered = title.lower()
    collapsed = _SLUG_COLLAPSE_RE.sub("-", lowered)
    return collapsed.strip("-")


def render_template(text: str, title: str, owner: str, date: str) -> str:
    """Fill in the H1, the header Owner line and section 0's author line; leave the rest.

    Works line by line on already newline-normalised text (see
    ``orient.read_text_tolerant``) and matches each target line by its
    fixed prefix, so section 9's unrelated ``Qn — owner: <name>`` example
    line — which shares the literal placeholder spelling ``<name>`` — is
    never touched.
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line == "# <Capability>":
            lines[i] = f"# {title}"
        elif line.startswith("Owner:") and "<name>" in line and "YYYY-MM-DD" in line:
            lines[i] = line.replace("<name>", owner, 1).replace("YYYY-MM-DD", date, 1)
        elif line.startswith("*(author:") and "<name>" in line and "<date>" in line:
            lines[i] = line.replace("<name>", owner, 1).replace("<date>", date, 1)
    return "\n".join(lines)


def resolve_docs_home(cwd: str, docs_home_arg: Optional[str]) -> Optional[str]:
    """``--docs-home`` wins outright; otherwise ask ``orient.py`` to resolve one."""
    if docs_home_arg:
        return docs_home_arg
    orientation = orient.build_orientation(None, cwd)
    return orientation.get("docsHome")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_outcome.py",
        description="Render a new outcome doc from the template, with the header fields filled in.",
    )
    parser.add_argument("--title", required=True, help="the capability's title; becomes the doc's H1")
    parser.add_argument("--owner", required=True, help="doc owner, for the header line and the section 0 author line")
    parser.add_argument("--date", default=None, help="ISO date for Last decision / the author line (default: today)")
    parser.add_argument("--docs-home", default=None, help="destination folder (default: orient.py's resolution)")
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="print the rendered text; write nothing")
    parser.add_argument(
        "--json", action="store_true", help="print {path, written, slug} instead of text or a confirmation line"
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"render_outcome.py: no such directory: {cwd}", file=sys.stderr)
        return 2

    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.normpath(os.path.join(script_dir, TEMPLATE_RELATIVE_PATH))
    try:
        template_text = orient.read_text_tolerant(template_path)
    except OSError as exc:
        print(f"render_outcome.py: could not read template at {template_path}: {exc}", file=sys.stderr)
        return 2

    docs_home = resolve_docs_home(cwd, args.docs_home)
    if not docs_home:
        print("render_outcome.py: no docs home; pass --docs-home", file=sys.stderr)
        return 2

    docs_home_abs = docs_home if os.path.isabs(docs_home) else os.path.join(cwd, docs_home)
    slug = slugify(args.title)
    dest_path = os.path.join(docs_home_abs, slug + ".md")

    if os.path.isfile(dest_path):
        print(f"render_outcome.py: {dest_path} already exists; refusing to overwrite", file=sys.stderr)
        return 2

    date = args.date or datetime.date.today().isoformat()
    rendered = render_template(template_text, args.title, args.owner, date)

    written = False
    if not args.dry_run:
        os.makedirs(docs_home_abs, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(rendered)
        written = True

    if args.json:
        result: Dict[str, Any] = {"path": dest_path, "written": written, "slug": slug}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.dry_run:
        sys.stdout.write(rendered)
    else:
        print(f"wrote {dest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
