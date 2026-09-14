#!/usr/bin/env python3
"""Adopt the promise skill into a project: config file + CLAUDE.md section.

    python3 adopt.py --cwd /path/to/project
    python3 adopt.py --cwd /path/to/project --dry-run
    python3 adopt.py --docs-home docs/rfcs --no-config

A project is "adopted" once it has a `.claude/promise.config.json` (or a
root `promise.config.json` fallback) and its CLAUDE.md carries the
promise section (references/architecture.md §13), so every person and
agent working there is routed to `/promise` instead of writing a design,
plan or spec doc by hand.

The config it writes carries ``"version": 1``, ``docsHome`` when one is
known, and — when at least one verify command was detected — a
``commands`` object with all three keys, the undetected ones as null,
because once that object exists detection is off for all three and the
file should show it. ``map`` is written as null with a comment.

Never overwrites an existing config, at either the primary or the
fallback location — when one is already loaded, this script writes no
second one and reports where the loaded one lives. Idempotent: running
it again with the same inputs changes no bytes and reports "changed":
false. A hand-edited interior of the managed CLAUDE.md block is restored
to the rendered form, with one line on stderr saying so; content outside
the ``<!-- promise:begin`` / ``<!-- promise:end -->`` markers is left
untouched, byte for byte, including its own line-ending style and a
leading BOM (whitespace around the end marker is tolerated). Every file
this script writes goes through a temporary file in the same directory
followed by ``os.replace``, so a reader never observes a half-written
file; the write goes to the real path behind a symlink, so a
``CLAUDE.md -> AGENTS.md`` link keeps pointing where it did, and an
existing file keeps its mode (a new one gets what ``open`` would have
given it under the current umask). ``--dry-run`` writes nothing and
prints a unified diff to stderr; the JSON result is always the only line
on stdout.

A ``--docs-home`` written with backslashes is recorded with forward
slashes (the config contract's form), with one line on stderr saying so.
When a fresh config would pin no docsHome at all — nothing detected and
no ``--docs-home`` given — one line on stderr says that every later
``new`` will ask where docs live; the JSON result carries ``docsHome`` so
a caller can see what was pinned.

Exit 0 on success or no-op. Exit 2 on a usage error, and also when the
CLAUDE.md markers cannot be resolved safely — an unmatched or duplicated
``<!-- promise:begin`` — when a path this script would write is a
directory (or sits under a file), when CLAUDE.md is not UTF-8, when
``--docs-home`` is absolute, escapes the project, or carries a line
break or a marker string, or when ``--docs-home`` disagrees with the
docsHome of a config that is already loaded (the config is edited, not
argued with; a CLAUDE.md naming one folder beside a config naming another
is the drift this script exists to prevent). In every one of those cases
nothing is written at all and the JSON result still prints, with
"changed": false, so a caller can always parse stdout as JSON.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import stat
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

BEGIN_PREFIX = "<!-- promise:begin"
END_MARKER = "<!-- promise:end -->"
TEMPLATE_NAME = "claude-md-section.md"
UNKNOWN_DOCS_HOME_TEXT = "the project's docs home"
BUNDLED_FRAMEWORK_TEXT = "the copy bundled with the promise skill"
UTF8_BOM = b"\xef\xbb\xbf"
CONFIG_VERSION = 1
VERIFY_COMMAND_KEYS = ("typeCheck", "test", "lint")


class MalformedMarkersError(Exception):
    """The CLAUDE.md promise markers cannot be resolved to a safe edit.

    Raised for anything other than "no markers at all" or "exactly one
    begin followed by exactly one end" — a begin with no end, an end
    with no begin, two begins, or an end that comes before its begin.
    Guessing at which lines belong to the managed block in any of these
    shapes risks deleting content a person wrote by hand, so the caller
    is expected to catch this, write nothing, and ask a human to fix the
    markers first.
    """

    def __init__(self, begin_lines: List[int], end_lines: List[int]):
        self.begin_lines = begin_lines
        self.end_lines = end_lines
        super().__init__(self._describe())

    def _describe(self) -> str:
        # 1-based line numbers, matching what an editor shows.
        begin_display = ", ".join(str(i + 1) for i in self.begin_lines) or "none"
        end_display = ", ".join(str(i + 1) for i in self.end_lines) or "none"
        return (
            "cannot resolve the promise:begin/end markers in CLAUDE.md "
            f"(begin at line {begin_display}; end at line {end_display}); "
            "fix the markers by hand, then run again"
        )


def render_section(docs_home: Optional[str], config_path: str, framework_path: str, skill_dir: str) -> str:
    """Render templates/claude-md-section.md with {docsHome}/{configPath}/{frameworkPath}.

    Each placeholder is substituted with ``str.replace``, one at a time,
    rather than ``str.format`` — the template's own prose may contain
    other ``{``/``}`` characters that a format-string parse would choke on.
    The backticks belong to the value, not the template: a real path is
    rendered as code (`docs/designs`) and a prose fallback ("the project's
    docs home") as prose, so a template that still backtick-quotes a
    placeholder has those backticks folded into the value's own.
    ``config_path`` and ``framework_path`` arrive already made portable by
    ``display_paths``: a CLAUDE.md is committed and shared, so it must never
    carry one machine's absolute paths.
    """
    template_path = os.path.join(skill_dir, "templates", TEMPLATE_NAME)
    text = orient.read_text_tolerant(template_path)
    for placeholder in ("{docsHome}", "{configPath}", "{frameworkPath}"):
        text = text.replace(f"`{placeholder}`", placeholder)
    text = text.replace("{docsHome}", f"`{docs_home}`" if docs_home else UNKNOWN_DOCS_HOME_TEXT)
    text = text.replace("{configPath}", config_path)
    text = text.replace("{frameworkPath}", framework_path)
    return text.rstrip("\n") + "\n"


def display_paths(cwd: str, config_path: str, orientation: Dict[str, Any]) -> Tuple[str, str]:
    """Project-relative config path (as code), and a framework reference
    that is true on every machine: the project's own copy as code, or the
    bundled copy as prose."""
    config_display = "`" + os.path.relpath(config_path, cwd).replace(os.sep, "/") + "`"
    fw = orientation.get("frameworkPath")
    if orientation.get("frameworkSource") == "project" and fw:
        framework_display = "`" + os.path.relpath(fw, cwd).replace(os.sep, "/") + "`"
    else:
        framework_display = BUNDLED_FRAMEWORK_TEXT
    return config_display, framework_display


def build_config(effective_docs_home: Optional[str], commands: Dict[str, Any]) -> Dict[str, Any]:
    """The config a fresh adoption writes.

    ``commands`` is written only when at least one command was detected,
    and then with all three keys — the undetected ones as null — because
    a ``commands`` object switches detection off for all three, and the
    file should show which ones it pinned to nothing. With nothing
    detected the object is omitted, which leaves detection on.
    """
    config: Dict[str, Any] = {"version": CONFIG_VERSION}
    if effective_docs_home:
        config["docsHome"] = effective_docs_home
    command_fields = {
        k: (commands.get(k) if isinstance(commands.get(k), str) and commands.get(k) else None)
        for k in VERIFY_COMMAND_KEYS
    }
    if any(command_fields.values()):
        config["commands"] = command_fields
    config["map"] = None
    config["$comment"] = (
        "map is not configured yet. See references/config.md for the shape "
        "(recipe, index, find/row/nextId commands, lanes, checks) and fill "
        "it in once this project has a capability map."
    )
    return config


def _scan_markers(lines: List[str]) -> Tuple[List[int], List[int]]:
    """Every line index carrying a begin marker, and every line index that
    is the end marker (surrounding whitespace tolerated) — the full
    picture, not just the first of each, so a caller can tell a
    well-formed file from a malformed one."""
    begin_lines = []
    end_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(BEGIN_PREFIX):
            begin_lines.append(i)
        if stripped == END_MARKER:
            end_lines.append(i)
    return begin_lines, end_lines


def apply_claude_md(existing_text: Optional[str], rendered_section: str) -> str:
    """Insert or replace the managed block; content outside it is untouched.

    No file, or a file with no markers at all: append the section after
    exactly one blank line. Exactly one begin followed by exactly one
    end: replace the block in place. Anything else — a begin with no
    end, an end with no begin, two begins, an end before its begin —
    raises MalformedMarkersError rather than guessing, because a wrong
    guess here deletes content a person wrote by hand.
    """
    section_text = rendered_section.rstrip("\n")
    if not existing_text:
        return section_text + "\n"

    lines = existing_text.splitlines(keepends=True)
    begin_lines, end_lines = _scan_markers(lines)

    if not begin_lines and not end_lines:
        # No existing block: append after exactly one blank line.
        return existing_text.rstrip("\n") + "\n\n" + section_text + "\n"

    if len(begin_lines) == 1 and len(end_lines) == 1 and begin_lines[0] < end_lines[0]:
        begin_idx, end_idx = begin_lines[0], end_lines[0]
        before = "".join(lines[:begin_idx])
        after = "".join(lines[end_idx + 1 :])
        return before + section_text + "\n" + after

    raise MalformedMarkersError(begin_lines, end_lines)


def has_managed_block(existing_text: Optional[str]) -> bool:
    """True when the text carries exactly one well-formed managed block."""
    if not existing_text:
        return False
    begin_lines, end_lines = _scan_markers(existing_text.splitlines(keepends=True))
    return len(begin_lines) == 1 and len(end_lines) == 1 and begin_lines[0] < end_lines[0]


def _detect_newline_and_bom(path: str) -> Tuple[str, bool]:
    """The file's dominant line ending and whether it opens with a UTF-8
    BOM, read from raw bytes so CRLF is never normalised away before it
    can be counted. Defaults to ("\\n", False) — plain UTF-8, no BOM —
    when the file cannot be read at all, which is the shape a brand new
    file is written in.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return "\n", False
    had_bom = raw.startswith(UTF8_BOM)
    if had_bom:
        raw = raw[len(UTF8_BOM) :]
    crlf_count = raw.count(b"\r\n")
    lf_count = raw.count(b"\n") - crlf_count  # bare LF, excluding CRLF's own LF
    dominant = "\r\n" if crlf_count > lf_count else "\n"
    return dominant, had_bom


def _encode_claude_md(new_text: str, dominant_newline: str, had_bom: bool) -> bytes:
    """The exact bytes to write for CLAUDE.md: new_text (canonical,
    "\\n"-delimited) re-expressed in the file's own dominant line ending,
    with its BOM reinstated if it had one."""
    if dominant_newline != "\n":
        new_text = new_text.replace("\n", dominant_newline)
    data = new_text.encode("utf-8")
    return (UTF8_BOM + data) if had_bom else data


def _new_file_mode() -> int:
    """The mode ``open(2)`` would give a brand new file under the current
    umask. Reading the umask means setting it and putting it back; that
    is not thread-safe, and is fine here because this script is
    single-threaded."""
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write data to path via a temporary file in the same directory,
    then os.replace — so a reader (or a crash) never observes a
    partially written file, and the write is a rename on every platform
    where the target and the temp file share a filesystem.

    Writes through a symlink rather than severing it: the target is
    ``os.path.realpath(path)``, so a ``CLAUDE.md -> AGENTS.md`` link
    keeps pointing at the file that now carries the section. An existing
    file keeps its own mode; a new file gets what ``open`` would have
    given it, never mkstemp's 0600.
    """
    path = os.path.realpath(path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = _new_file_mode()
    fd, tmp_path = tempfile.mkstemp(prefix=".promise-adopt-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _unwritable_reason(path: str, label: str) -> Optional[str]:
    """Why ``path`` cannot be written as a regular file, or None.

    A path that exists but is not a regular file (a directory, say), or
    whose nearest existing ancestor is not a directory (``.claude`` is a
    file), is refused up front — never left to ``os.replace`` to
    traceback on.
    """
    if os.path.lexists(path) and not os.path.isfile(path):
        return f"{label} exists but is not a regular file: {path}"
    parent = os.path.dirname(path) or "."
    while not os.path.lexists(parent):
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    if os.path.lexists(parent) and not os.path.isdir(parent):
        return f"{label} cannot be created under {parent}: not a directory"
    return None


def _docs_home_reason(value: str) -> Optional[str]:
    """Why ``value`` cannot be recorded as docsHome, or None.

    docsHome is written into JSON and substituted into a CLAUDE.md line,
    so it must be one line, must not carry a marker string (which would
    break the managed block on the next run), and must stay inside the
    project like every other configured path.
    """
    if "\n" in value or "\r" in value:
        return "--docs-home must be a single line"
    if BEGIN_PREFIX in value or END_MARKER in value:
        return "--docs-home must not contain a promise:begin/end marker"
    if orient._path_escapes(value):
        # orient's rule, not a second copy of it: absolute on either OS
        # (a drive letter included) or climbing out with '..'.
        return "--docs-home must be relative to the project root and must not escape it ('..')"
    return None


def _refused(result: Dict[str, Any], reason: str) -> int:
    """Print the reason to stderr and the (unchanged) JSON result to
    stdout, and return exit 2 — nothing has been written."""
    print(f"adopt.py: {reason}", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2


def main(argv: Optional[list] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
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

    # --- Resolve where the config lives (or would live), never shadowing
    # an already-loaded one at either the primary or the fallback path
    # (architecture.md §6's own load order) with a second, poorer copy. ---
    config_path = os.path.join(cwd, ".claude", "promise.config.json")
    config_reason_skipped: Optional[str] = None
    will_write_new_config = False

    if orientation["config"]["loaded"] and orientation["config"]["path"]:
        config_path = orientation["config"]["path"]
        if not args.no_config:
            config_reason_skipped = (
                f"config already loaded from {config_path}; not writing a second one"
            )
    elif not args.no_config:
        if os.path.isfile(config_path):
            config_reason_skipped = f"config already exists at {config_path}; not overwriting"
        else:
            will_write_new_config = True

    claude_md_path = orientation["claudeMd"]["path"] or os.path.join(cwd, "CLAUDE.md")

    refused_result = {
        "configWritten": False,
        "configPath": config_path,
        "claudeMdWritten": False,
        "claudeMdPath": claude_md_path,
        "docsHome": effective_docs_home,
        "changed": False,
        "dryRun": args.dry_run,
    }

    # --- Refuse anything that could not be written safely, before either
    # file is touched: a wrong-typed path, a docsHome that would break the
    # managed block, a CLAUDE.md that is not text. ---
    if args.docs_home is not None:
        reason = _docs_home_reason(args.docs_home)
        if reason is not None:
            return _refused(refused_result, reason)
        if "\\" in args.docs_home:
            # The config contract asks for forward slashes; orient would
            # otherwise warn about this file on every later run.
            effective_docs_home = args.docs_home.replace("\\", "/")
            print(
                f"adopt.py: --docs-home uses backslashes; recorded as {effective_docs_home!r}",
                file=sys.stderr,
            )
        if orientation["config"]["loaded"] and effective_docs_home != orientation["docsHome"]:
            return _refused(
                refused_result,
                f"--docs-home {effective_docs_home!r} disagrees with the loaded config's "
                f"docsHome {orientation['docsHome']!r} ({orientation['docsHomeSource']}); "
                "edit the config, then rerun without the flag",
            )
    elif effective_docs_home and ("\n" in effective_docs_home or "\r" in effective_docs_home):
        return _refused(refused_result, "docsHome from the config must be a single line")

    if will_write_new_config:
        reason = _unwritable_reason(config_path, "config path")
        if reason is not None:
            return _refused(refused_result, reason)
    if not args.no_claude_md:
        reason = _unwritable_reason(claude_md_path, "CLAUDE.md")
        if reason is not None:
            return _refused(refused_result, reason)

    # --- Resolve the CLAUDE.md edit up front, without writing anything,
    # so a malformed-marker file can refuse the whole run before either
    # file is touched. ---
    claude_md_new_text: Optional[str] = None
    claude_md_marker_error: Optional[str] = None
    existing_claude_md_text: Optional[str] = None
    if os.path.isfile(claude_md_path):
        try:
            existing_claude_md_text = orient.read_text_tolerant(claude_md_path)
        except UnicodeDecodeError as exc:
            return _refused(refused_result, f"CLAUDE.md is not UTF-8 text ({claude_md_path}): {exc}")
        except OSError as exc:
            return _refused(refused_result, f"cannot read CLAUDE.md ({claude_md_path}): {exc}")

    if not args.no_claude_md:
        config_display, framework_display = display_paths(cwd, config_path, orientation)
        rendered = render_section(effective_docs_home, config_display, framework_display, skill_dir)
        try:
            claude_md_new_text = apply_claude_md(existing_claude_md_text, rendered)
        except MalformedMarkersError as exc:
            claude_md_marker_error = str(exc)

    if claude_md_marker_error is not None:
        return _refused(refused_result, claude_md_marker_error)

    # --- Everything above was read-only. From here, actually write (or,
    # under --dry-run, only report and diff). ---
    config_written = False
    config_diff = ""

    if config_reason_skipped is not None:
        print(f"adopt.py: {config_reason_skipped}", file=sys.stderr)
    elif will_write_new_config:
        if not effective_docs_home:
            print(
                "adopt.py: no docs folder detected and no --docs-home given; the config "
                "will pin no docsHome and every later `new` will ask where docs live — "
                "pass --docs-home <dir> (adopt.md's default is docs/designs)",
                file=sys.stderr,
            )
        new_config = build_config(effective_docs_home, orientation["commands"])
        new_config_text = json.dumps(new_config, indent=2, ensure_ascii=False) + "\n"
        if args.dry_run:
            rel = os.path.relpath(config_path, cwd)
            config_diff = "".join(
                difflib.unified_diff([], new_config_text.splitlines(keepends=True), fromfile=rel, tofile=rel)
            )
        else:
            _atomic_write_bytes(config_path, new_config_text.encode("utf-8"))
            config_written = True

    claude_md_written = False
    claude_md_changed = False
    claude_md_diff = ""

    if not args.no_claude_md:
        claude_md_changed = existing_claude_md_text != claude_md_new_text
        if claude_md_changed:
            if has_managed_block(existing_claude_md_text):
                print(
                    "adopt.py: the managed promise block in CLAUDE.md differed from the rendered "
                    "form; it is restored (content outside the markers is untouched)",
                    file=sys.stderr,
                )
            if args.dry_run:
                rel = os.path.relpath(claude_md_path, cwd)
                claude_md_diff = "".join(
                    difflib.unified_diff(
                        (existing_claude_md_text or "").splitlines(keepends=True),
                        (claude_md_new_text or "").splitlines(keepends=True),
                        fromfile=rel,
                        tofile=rel,
                    )
                )
            else:
                dominant_newline, had_bom = _detect_newline_and_bom(claude_md_path)
                data = _encode_claude_md(claude_md_new_text or "", dominant_newline, had_bom)
                _atomic_write_bytes(claude_md_path, data)
                claude_md_written = True

    if args.dry_run:
        changed = bool(will_write_new_config or claude_md_changed)
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
        "docsHome": effective_docs_home,
        "changed": changed,
        "dryRun": args.dry_run,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
