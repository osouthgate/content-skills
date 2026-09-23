#!/usr/bin/env python3
"""Start a capability map in an adopted project, from the starter template.

    python3 start_map.py --cwd /path/to/project --dry-run
    python3 start_map.py --cwd /path/to/project [--dest docs/capabilities]

Copies ``templates/starter-map/`` into ``--dest`` (default
``docs/capabilities``) — ``map.json`` with no rows, ``capability_find.py``
(its only reader) and ``recipe.md`` (how a row is added) — and points the
project's promise config at them: the ``map`` object gets ``recipe``,
``find``, ``row``, ``nextId``, ``rowIdPattern``, ``lanes`` and ``checks``,
so ``orient.py`` reports ``mapUsable: true`` straight after. From then on
the three files are the project's own: the skill never rewrites them.

Refuses (exit 2, nothing written) when the project has no loaded config
(run ``adopt.py`` first), when the config already carries a ``map`` object
(a project's own map is never replaced, even a partial one — finish it by
hand), when ``--dest`` escapes the project or already holds files, or when
a path it would write is not writable. ``--dry-run`` writes nothing and
prints every file it would write, and the config diff, to stderr. The JSON
result is always the only line on stdout.

The config is rewritten as two-space JSON with its keys in their existing
order and ``map`` set in place; the top-level ``$comment`` is dropped only
when it is ``adopt.py``'s own "map is not configured yet" note, which would
now be false. The rewrite goes through a temporary file and ``os.replace``,
like ``adopt.py``'s.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import posixpath
import sys
from typing import Any, Dict, List, Optional

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import adopt  # noqa: E402  (sibling-script import; see path insert above)
import orient  # noqa: E402

DEFAULT_DEST = "docs/capabilities"
TEMPLATE_DIR = os.path.join(os.path.dirname(_SCRIPTS_DIR), "templates", "starter-map")
FILES = ("map.json", "capability_find.py", "recipe.md")
LANES = {
    "data": "tests[]",
    "response": "tests[]",
    "perception": "e2eTests[]",
    "judgement": "evalTests[]",
    "sibling": "siblingTests[]",
}


def map_config(dest: str) -> Dict[str, Any]:
    """The config ``map`` object for a starter map installed at ``dest``
    (project-relative, forward slashes). Every command is an argv line run
    from the project root with no shell, as ``adapter.py`` requires."""
    reader = f"python3 {dest}/capability_find.py"
    return {
        "$comment": "Started from the promise skill's starter map (scripts/start_map.py). The map, its reader and its recipe are this project's own files now; change them there, and this object with them.",
        "recipe": f"{dest}/recipe.md",
        "find": reader,
        "row": f"{reader} --row",
        "nextId": f"{reader} --next-id",
        "rowIdPattern": "^CAP-\\d+$",
        "lanes": dict(LANES),
        "checks": [f"{reader} --check"],
    }


def render_files(dest: str) -> Dict[str, str]:
    """Each starter file's text, with its placeholders filled for ``dest``:
    ``{dir}`` in the recipe is the destination, ``{docRoot}`` in the map is
    the project root relative to the map, so a row's ``doc`` is its
    project-relative path."""
    doc_root = "/".join([".."] * len(dest.split("/")))
    out: Dict[str, str] = {}
    for name in FILES:
        with open(os.path.join(TEMPLATE_DIR, name), encoding="utf-8") as fh:
            text = fh.read()
        if name == "recipe.md":
            text = text.replace("{dir}", dest)
        elif name == "map.json":
            text = text.replace("{docRoot}", doc_root)
        out[name] = text
    return out


def _dest_reason(dest: str) -> Optional[str]:
    if "\n" in dest or "\r" in dest or not dest.strip() or dest == ".":
        return "--dest must be a single line naming a folder below the project root"
    if " " in dest:
        return "--dest must not contain a space (it is written into argv lines)"
    if orient._path_escapes(dest):
        return "--dest must be relative to the project root and must not escape it ('..')"
    return None


def _refused(result: Dict[str, Any], reason: str) -> int:
    print(f"start_map.py: {reason}", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="start_map.py",
        description="Start a capability map from the promise skill's starter template.",
    )
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--dest", default=DEFAULT_DEST, help=f"folder for the map, project-relative (default: {DEFAULT_DEST})")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; print what would be written to stderr")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    dest = posixpath.normpath(args.dest.replace("\\", "/")) if args.dest.strip() else ""
    result: Dict[str, Any] = {
        "dest": dest,
        "configPath": None,
        "files": [f"{dest}/{name}" for name in FILES],
        "filesWritten": [],
        "configWritten": False,
        "changed": False,
        "dryRun": args.dry_run,
    }
    if not os.path.isdir(cwd):
        return _refused(result, f"no such directory: {cwd}")
    reason = _dest_reason(dest)
    if reason:
        return _refused(result, reason)

    config, config_path, _warnings = orient.load_config(cwd)
    result["configPath"] = config_path
    if config is None:
        return _refused(
            result,
            "no readable promise config in this project; run adopt.py first, then start the map",
        )
    if config.get("map") is not None:
        return _refused(
            result,
            f"{config_path} already has a map object; a project's own map is never replaced — finish or remove it by hand",
        )

    dest_abs = os.path.join(cwd, *dest.split("/"))
    if os.path.lexists(dest_abs) and not os.path.isdir(dest_abs):
        return _refused(result, f"{dest} exists but is not a directory")
    if os.path.isdir(dest_abs) and os.listdir(dest_abs):
        return _refused(result, f"{dest} already holds files; pick an empty or new folder with --dest")
    for name in FILES:
        reason = adopt._unwritable_reason(os.path.join(dest_abs, name), name)
        if reason:
            return _refused(result, reason)
    reason = adopt._unwritable_reason(config_path, "config path")
    if reason:
        return _refused(result, reason)

    files = render_files(dest)
    new_config = dict(config)
    new_config["map"] = map_config(dest)
    if new_config.get("$comment") == adopt.NULL_MAP_COMMENT:
        # adopt.py's "map is not configured yet" note would now be false.
        del new_config["$comment"]
    with open(config_path, encoding="utf-8-sig") as fh:
        old_config_text = fh.read()
    new_config_text = json.dumps(new_config, indent=2, ensure_ascii=False) + "\n"

    if args.dry_run:
        for name in FILES:
            print(f"--- would write {dest}/{name} ({len(files[name].splitlines())} lines)", file=sys.stderr)
        rel = os.path.relpath(config_path, cwd).replace(os.sep, "/")
        sys.stderr.writelines(
            difflib.unified_diff(
                old_config_text.splitlines(keepends=True),
                new_config_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    for name in FILES:
        adopt._atomic_write_bytes(os.path.join(dest_abs, name), files[name].encode("utf-8"))
        result["filesWritten"].append(f"{dest}/{name}")
    adopt._atomic_write_bytes(config_path, new_config_text.encode("utf-8"))
    result["configWritten"] = True
    result["changed"] = True
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
