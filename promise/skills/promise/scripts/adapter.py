#!/usr/bin/env python3
"""Run a project's configured map and verification commands safely.

    python3 adapter.py [--cwd DIR] [--json] find "<query>"
    python3 adapter.py [--cwd DIR] [--json] row <id>
    python3 adapter.py [--cwd DIR] [--json] next-id
    python3 adapter.py [--cwd DIR] [--json] checks
    python3 adapter.py [--cwd DIR] [--json] verify
    python3 adapter.py [--cwd DIR] show

A mode never composes a shell string from a configured command plus
user-supplied text. Every configured command string is split with
``shlex.split`` into its own argv, and a caller-supplied argument — a
search query, a row id — is appended as exactly one more argv element,
never interpolated into text a shell would parse. Every child process
runs with ``shell=False``, so a hostile query containing ``$(...)`` or
backticks is inert: it becomes one string in argv, nothing more, and
nothing it contains ever executes.

Config is resolved through ``orient.py`` — this script parses no config
file of its own; ``map`` and ``commands`` come straight from its
orientation JSON. ``find``, ``row`` and ``next-id`` each run one
configured command and report one result. ``row`` additionally validates
the id against ``map.rowIdPattern`` when the project sets one, and
refuses — without running anything — on a mismatch. ``checks`` runs
``map.checks`` in the configured order and stops at the first non-zero
exit. ``verify`` runs ``commands.typeCheck``, ``commands.test`` and
``commands.lint`` in that order, skipping any that are not configured,
and also stops at the first non-zero exit. ``show`` prints every command
each op would run, one per line, in the same "label: command" shape, and
runs nothing at all.

A request that cannot even be attempted — no map configured, the specific
command an op needs is absent, or a row id that fails
``map.rowIdPattern`` — refuses with exit 2 and a one-line reason on
stderr, always plain text regardless of ``--json``, because there is no
child result to report. A configured executable that does not exist
exits 127 with a one-line reason instead of a traceback; this is treated
as an attempted run, so it does appear in ``--json`` output with
``"exit": 127``.

Once a command actually runs, ``--json`` prints one object
``{"op", "argv", "exit", "stdout", "stderr"}`` for a single-command op, or
a JSON array of that shape, one entry per step actually attempted, for
``checks``/``verify``. Without ``--json``, each child's own stdout and
stderr stream straight to this process's stdout and stderr as it runs,
and the process exits with the exit code of the last step attempted (0
when every step — or zero steps — succeeded).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

VERIFY_COMMAND_ORDER = ("typeCheck", "test", "lint")

_MAP_COMMAND_LABELS = (("find", "map.find"), ("row", "map.row"), ("nextId", "map.nextId"))


def _refuse(reason: str) -> int:
    """Print one plain reason line to stderr and return the exit code 2 to use.

    Used for every refusal that happens before any command is attempted —
    a missing map, a missing configured command, a row id that fails
    ``map.rowIdPattern`` — so nothing downstream mistakes a refusal for a
    result whose ``--json`` object it should try to parse.
    """
    print(f"adapter.py: {reason}", file=sys.stderr)
    return 2


def split_command(command: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """Split a configured command string into argv with ``shlex.split``.

    Returns ``(argv, None)`` on success or ``(None, reason)`` when the
    string is empty or is not valid shell-word syntax (an unclosed quote,
    for instance) — a misconfigured project, not a crash.
    """
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, f"could not parse configured command {command!r}: {exc}"
    if not argv:
        return None, f"configured command is empty: {command!r}"
    return argv, None


def run_argv(argv: List[str], cwd: str, op: str) -> Dict[str, Any]:
    """Run one child process and report the outcome; never raises.

    A missing or unrunnable executable (``OSError`` — most commonly
    ``FileNotFoundError``) is reported as exit 127 in the same shape a
    real exit code would be, so a caller building a ``checks``/``verify``
    sequence can treat "not found" exactly like any other non-zero exit
    for the purpose of deciding whether to keep going.
    """
    try:
        proc = subprocess.run(argv, shell=False, cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        return {
            "op": op,
            "argv": argv,
            "exit": 127,
            "stdout": "",
            "stderr": f"executable not found: {argv[0]} ({exc})",
        }
    return {"op": op, "argv": argv, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def emit_single(result: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(result["stdout"])
        sys.stderr.write(result["stderr"])


def run_sequence(steps: List[Tuple[str, str]], cwd: str, as_json: bool) -> Tuple[List[Dict[str, Any]], int]:
    """Run ``(op_label, command_string)`` pairs in order; stop at the first failure.

    A command string that fails to split is reported as its own step
    result with ``"exit": 2`` rather than raising, so one malformed entry
    in a project's ``map.checks`` still stops the sequence cleanly instead
    of crashing this process. Streams each step's captured stdout/stderr
    as it finishes when ``as_json`` is false, so output appears in the
    order the steps actually ran. Returns ``(results, exit_code)``;
    ``exit_code`` is 0 when ``steps`` is empty or every attempted step
    exited 0.
    """
    results: List[Dict[str, Any]] = []
    exit_code = 0
    for op_label, command in steps:
        argv, reason = split_command(command)
        if argv is None:
            result: Dict[str, Any] = {"op": op_label, "argv": [], "exit": 2, "stdout": "", "stderr": reason or ""}
        else:
            result = run_argv(argv, cwd, op_label)
        results.append(result)
        if not as_json:
            sys.stdout.write(result["stdout"])
            sys.stderr.write(result["stderr"])
        exit_code = result["exit"]
        if exit_code != 0:
            break
    return results, exit_code


def run_single_map_command(
    map_value: Optional[dict], key: str, op_label: str, extra_arg: Optional[str], cwd: str, as_json: bool
) -> int:
    """Resolve ``map.<key>``, append ``extra_arg`` (if any) as one argv element, and run it."""
    if not isinstance(map_value, dict):
        return _refuse(f"no map configured (needed for '{op_label}')")
    command = map_value.get(key)
    if not command:
        return _refuse(f"map.{key} is not configured")
    argv, reason = split_command(command)
    if argv is None:
        return _refuse(reason or f"map.{key} could not be parsed")
    if extra_arg is not None:
        argv = argv + [extra_arg]
    result = run_argv(argv, cwd, op_label)
    emit_single(result, as_json)
    return result["exit"]


def run_row(map_value: Optional[dict], row_id: str, cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'row')")
    pattern = map_value.get("rowIdPattern")
    if pattern:
        try:
            compiled = re.compile(pattern)
        except re.error:
            compiled = None  # an invalid pattern cannot be checked against; fall through and run
        if compiled is not None and compiled.fullmatch(row_id) is None:
            return _refuse(f"row id {row_id!r} does not match map.rowIdPattern {pattern!r}")
    return run_single_map_command(map_value, "row", "row", row_id, cwd, as_json)


def run_checks(map_value: Optional[dict], cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'checks')")
    checks = map_value.get("checks")
    if checks is None:
        return _refuse("map.checks is not configured")
    if not isinstance(checks, list):
        return _refuse("map.checks is not a list")
    steps = [(f"checks[{i}]", command) for i, command in enumerate(checks) if command]
    results, exit_code = run_sequence(steps, cwd, as_json)
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return exit_code


def run_verify(commands: Optional[dict], cwd: str, as_json: bool) -> int:
    commands = commands or {}
    steps = [(name, commands.get(name)) for name in VERIFY_COMMAND_ORDER]
    steps = [(name, command) for name, command in steps if command]
    results, exit_code = run_sequence(steps, cwd, as_json)
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return exit_code


def show_commands(map_value: Optional[dict], commands: Optional[dict]) -> None:
    """Print every configured command, one per line, as ``<label>: <command>``. Runs nothing."""
    lines: List[str] = []
    if isinstance(map_value, dict):
        for key, label in _MAP_COMMAND_LABELS:
            command = map_value.get(key)
            if command:
                lines.append(f"{label}: {command}")
        checks = map_value.get("checks")
        if isinstance(checks, list):
            for i, command in enumerate(checks):
                if command:
                    lines.append(f"map.checks[{i}]: {command}")
    if isinstance(commands, dict):
        for name in VERIFY_COMMAND_ORDER:
            command = commands.get(name)
            if command:
                lines.append(f"commands.{name}: {command}")
    for line in lines:
        print(line)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adapter.py",
        description=(
            "Run a project's configured map/verify commands without ever composing a "
            "shell string from configuration plus user-supplied text."
        ),
    )
    parser.add_argument("--cwd", default=None, help="project root to resolve config against (default: current directory)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable result instead of streaming the child's own output",
    )
    subparsers = parser.add_subparsers(dest="op", required=True, metavar="{find,row,next-id,checks,verify,show}")

    find_parser = subparsers.add_parser("find", help="run map.find with a query appended as one argument")
    find_parser.add_argument("query", help="search text; passed verbatim as one argv element, never interpolated")

    row_parser = subparsers.add_parser("row", help="run map.row with a row id appended as one argument")
    row_parser.add_argument("id", help="row id; checked against map.rowIdPattern before anything runs")

    subparsers.add_parser("next-id", help="run map.nextId with no extra argument")
    subparsers.add_parser("checks", help="run each map.checks command in order; stop at the first failure")
    subparsers.add_parser(
        "verify", help="run commands.typeCheck, commands.test, commands.lint in order, skipping unset ones"
    )
    subparsers.add_parser("show", help="print every configured command, one per line; run nothing")

    return parser


def dispatch(args: argparse.Namespace, cwd: str) -> int:
    orientation = orient.build_orientation(None, cwd)
    map_value = orientation.get("map")
    commands = orientation.get("commands")

    if args.op == "show":
        show_commands(map_value, commands)
        return 0
    if args.op == "find":
        return run_single_map_command(map_value, "find", "find", args.query, cwd, args.json)
    if args.op == "row":
        return run_row(map_value, args.id, cwd, args.json)
    if args.op == "next-id":
        return run_single_map_command(map_value, "nextId", "next-id", None, cwd, args.json)
    if args.op == "checks":
        return run_checks(map_value, cwd, args.json)
    if args.op == "verify":
        return run_verify(commands, cwd, args.json)
    return _refuse(f"unknown operation: {args.op}")  # pragma: no cover - argparse prevents this


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        return _refuse(f"no such directory: {cwd}")

    try:
        return dispatch(args, cwd)
    except Exception as exc:  # pragma: no cover - last-resort guard, never a traceback for the caller
        return _refuse(f"internal error: {exc}")


if __name__ == "__main__":
    sys.exit(main())
