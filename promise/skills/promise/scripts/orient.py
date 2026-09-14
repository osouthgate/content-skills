#!/usr/bin/env python3
"""Phase 0 orientation for the promise skill.

Resolves the framework path, the project config, the docs home, the
project's type-check/test/lint commands, existing outcome docs, and
CLAUDE.md adoption state, then prints one JSON object to stdout.

See references/architecture.md §5 (schema and detection rules) and
§6 (config contract). For a valid invocation this script never exits
non-zero: every problem is recorded in the "warnings" list of the
emitted JSON instead of raising or failing the process, so a caller
can always parse stdout as JSON and always finds every schema key
present (null when unknown). Three things are not valid invocations
and exit 2 with one line on stderr: an argparse usage error (an
unrecognised flag, a missing value), a ``--cwd`` that is not a
directory, and an ``--input-file`` that cannot be read or is not UTF-8.

"mode" is the mode word passed with ``--mode`` (or "infer" for an
unrecognised word) and null when the flag was not given — the JSON
never claims a mode nobody asked for.

Config paths (docsHome, plansFolder, frameworkPath) are project-relative
with forward slashes; a value written with backslashes is normalised to
forward slashes and warned about, so a config written on one OS reads
the same on another. A configured docsHome, map.recipe or map.index
that does not exist on disk is warned about and still returned —
existence is reported, not enforced, so the first mode to use the path
can decide what to do.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

RECOGNISED_MODES = (
    "new", "revise", "review", "merge", "arm", "intake", "reconcile", "adopt",
)

# "version" is the config's version key; "$schema" is accepted for configs
# written before it existed and warned about as deprecated.
CONFIG_VERSION = 1

KNOWN_CONFIG_KEYS = {
    "$schema", "$comment", "version", "docsHome", "frameworkPath", "plansFolder",
    "commands", "map",
}

KNOWN_COMMANDS_KEYS = {"$schema", "$comment", "typeCheck", "test", "lint"}

KNOWN_MAP_KEYS = {
    "$schema", "$comment", "recipe", "index", "find", "row", "nextId",
    "rowIdPattern", "lanes", "checks", "issueTracker",
}

# The map keys that must all be present, as strings (lanes: as an object),
# before a map counts as configured — the mapUsable rule in
# architecture.md §5.
MAP_STRING_KEYS = ("recipe", "find", "row")

# The map keys that name a file in the project; each is warned about when
# it does not exist, without changing mapUsable.
MAP_FILE_KEYS = ("recipe", "index")

ISSUE_TRACKER_KEYS = ("kind", "repo", "template")

DOCS_HOME_CANDIDATES = (
    "docs/designs", "docs/design", "docs/specs", "docs/rfcs", "design", "docs",
)

TYPE_CHECK_SCRIPT_NAMES = ("type-check", "typecheck", "tsc")

PROMISE_BEGIN_MARKER = "<!-- promise:begin"

TLDR_HEADING = "## 0. TLDR"

H1_RE = re.compile(r"^#\s+(.+?)\s*$")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
LAST_DECISION_RE = re.compile(r"Last decision:\s*(\S+)")
TARGET_NAME_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)")

# --- FEATURE 1: --input mode suggestion (architecture.md §4 rules 1-10) ---

_MODE_WORD_PUNCT = ".,;:!?'\"()[]{}"

CRITIQUE_VERB_RE = re.compile(
    r"\b(?:review|critique|feedback|check|is this any good)\b", re.IGNORECASE
)
ARM_PHRASE_RE = re.compile(
    r"\b(?:arm|start building|red tests|kick off|file the rows)\b", re.IGNORECASE
)
RECONCILE_PHRASE_RE = re.compile(
    r"\b(?:shipped|landed|already do|already covered)\b"
    r"|isn't .* covered"
    r"|update the (?:map|row)",
    re.IGNORECASE,
)
# Feedback vocabulary, the router's own phrases, and the shape of a plain
# complaint sentence — "users say X is broken", "customers complain that"
# — so a single reported sentence leans intake the way a list does.
INTAKE_WORD_RE = re.compile(
    r"\b(?:feedback|complaints?|complain(?:s|ed|ing)?|bug reports|wishes|feature requests"
    r"|(?:users?|customers?|people|clients?) (?:say|said|keep saying|report(?:ed)?|are asking|want)"
    r"|is broken|are broken|does nothing|doesn'?t work|don'?t work|not working"
    r"|what does this map to|map this|turn this into (?:scenarios|gherkins|a scenario)"
    r"|which (?:capability|promise|row) covers|add this as a scenario)\b",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")
# "set up" as two separate words, e.g. "set this project up", not only the
# contiguous "set up"/"setup".
ADOPT_TRIGGER_RE = re.compile(
    r"\bset\b(?:\s+\S+){0,6}?\s+up\b|\bsetup\b|\binstall\b|\bconfigure\b|\badopt\b",
    re.IGNORECASE,
)
PROMISE_WORD_RE = re.compile(r"\bpromise\b", re.IGNORECASE)
# An adopt trigger word aimed at *this* project reads as adopt even when the
# word "promise" is never said — "install it here", "set this project up".
ADOPT_LOCAL_RE = re.compile(
    r"\b(?:this project|this repo(?:sitory)?|it here|here)\b", re.IGNORECASE
)
ROW_ID_TOKEN_RE = re.compile(r"[^\s,;]+")

# A generic change verb aimed at "the doc"/"the outcome" with no title named
# still means revise whenever at least one outcome doc exists — the doc is
# ambiguous, the mode is not.
GENERIC_CHANGE_VERB_RE = re.compile(r"\b(?:fix|update|change)\b", re.IGNORECASE)
DOC_REFERENCE_WORD_RE = re.compile(r"\b(?:doc|outcome)\b", re.IGNORECASE)

# A critique verb with no existing-doc match: pasted or external content,
# not a request about a doc already on file. "feedback" is deliberately not
# one of these — a bare "feedback" leans intake (INTAKE_WORD_RE), and this
# rule only runs once intake's own checks have had first refusal.
REVIEW_NO_DOC_VERB_RE = re.compile(
    r"\b(?:review|critique|check|is this any good)\b", re.IGNORECASE
)

# Reconcile patterns strong enough to stand alone: a commit sha, a feat/fix
# branch prefix, or a test-file path. A bare ticket number is not among
# them — see TICKET_NUMBER_RE and RECONCILE_ACCOMPANY_RE below. A sha here
# is a 7-40 hex run with at least one letter: a digit-only run is a date
# or an id as often as a sha, and gets the same treatment as "#1234567" —
# reconcile only beside a shipped/landed/commit word.
RECONCILE_STRONG_PATTERN_RE = re.compile(
    r"\b(?=[0-9a-f]{7,40}\b)[0-9]*[a-f][0-9a-f]*\b"
    r"|\b(?:feat|fix)/"
    r"|\.test\."
    r"|\.spec\."
    r"|/tests/"
    r"|/test/",
    re.IGNORECASE,
)
TICKET_NUMBER_RE = re.compile(r"#\d+")
# A bare ticket number reads as reconcile only alongside one of these — a
# ticket mentioned next to design/plan words, with nothing else, is a
# reference for a doc still to be written, not evidence anything shipped.
RECONCILE_ACCOMPANY_RE = re.compile(
    r"\b(?:shipped|landed|merged|pr|pull request|commit|branch)\b", re.IGNORECASE
)


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings.

    ``utf-8-sig`` strips a leading BOM if present and is otherwise a
    plain UTF-8 decode; the default universal-newlines text mode
    (``newline=None``) normalises CRLF and CR to LF.
    """
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def unfenced(lines: List[str]) -> List[str]:
    """The same list with every line inside a ``` / ~~~ fenced block (and
    the fence lines themselves) replaced by "", so a heading scan skips
    illustrations while indices still line up with the original.
    """
    out: List[str] = []
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def get_skill_dir() -> str:
    """Return the absolute path to skills/promise (the parent of scripts/)."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(scripts_dir)


def _path_escapes(value: str) -> bool:
    """True when a configured project-relative path is absolute or climbs
    out of the project with a ".." segment.

    Both slash styles are checked, and a Windows drive letter (``C:\\x``,
    ``C:/x``, the drive-relative ``D:docs``) counts as absolute on every
    OS -- ``os.path.isabs`` alone would pass it on POSIX -- so a config
    written on one OS is judged the same way on another. adopt.py applies
    this same rule to ``--docs-home``.
    """
    if os.path.isabs(value) or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        return True
    return ".." in re.split(r"[\\/]+", value)


def _normalise_slashes(value: str, key: str, warnings: List[str]) -> str:
    """Turn a backslash-separated config path into the forward-slash form
    the contract asks for, with a warning naming the key."""
    if "\\" in value:
        warnings.append(f"{key} uses backslashes; normalised to forward slashes: {value!r}")
        return value.replace("\\", "/")
    return value


def load_config(cwd: str) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Load .claude/promise.config.json, falling back to promise.config.json.

    Returns (raw_config_or_None, path_or_None, warnings). Unknown
    top-level keys warn; "$comment" is always ignored, at the top level
    and wherever else it appears. "version" is the config's version key;
    a top-level "$schema" is accepted with a deprecation warning.
    """
    warnings: List[str] = []
    candidates = [
        os.path.join(cwd, ".claude", "promise.config.json"),
        os.path.join(cwd, "promise.config.json"),
    ]
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            raw = json.loads(read_text_tolerant(candidate))
        except (OSError, ValueError) as exc:
            warnings.append(
                f"could not read or parse config at {candidate}: {exc}; using detection"
            )
            return None, candidate, warnings
        if not isinstance(raw, dict):
            warnings.append(
                f"config at {candidate} is not a JSON object; using detection"
            )
            return None, candidate, warnings
        unknown = sorted(k for k in raw.keys() if k not in KNOWN_CONFIG_KEYS)
        for key in unknown:
            warnings.append(f"unknown config key: {key}")
        if "$schema" in raw:
            warnings.append(
                '"$schema" is deprecated; replace it with "version": 1'
            )
        if "version" in raw and raw["version"] != CONFIG_VERSION:
            warnings.append(
                f"unsupported config version: {raw['version']!r}; this skill reads version {CONFIG_VERSION}"
            )
        return raw, candidate, warnings
    warnings.append("no config found at .claude/promise.config.json; using detection")
    return None, None, warnings


def detect_docs_home(cwd: str) -> Optional[str]:
    """Return the first existing candidate docs-home directory, or None."""
    for rel in DOCS_HOME_CANDIDATES:
        if os.path.isdir(os.path.join(cwd, rel)):
            return rel
    return None


def detect_plans_folder(cwd: str) -> Optional[str]:
    """Return "plans" if that directory exists under cwd, else None."""
    return "plans" if os.path.isdir(os.path.join(cwd, "plans")) else None


def _package_manager_prefix(cwd: str) -> str:
    if os.path.isfile(os.path.join(cwd, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.isfile(os.path.join(cwd, "yarn.lock")):
        return "yarn"
    # bun.lockb is the binary lockfile; bun.lock the text one Bun 1.2+ writes.
    if os.path.isfile(os.path.join(cwd, "bun.lockb")) or os.path.isfile(os.path.join(cwd, "bun.lock")):
        return "bun"
    return "npm run"


def _detect_commands_from_package_json(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "package.json")
    if not os.path.isfile(path):
        return None
    try:
        raw = json.loads(read_text_tolerant(path))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    scripts = raw.get("scripts")
    if not isinstance(scripts, dict):
        return None
    prefix = _package_manager_prefix(cwd)
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in scripts), None)
    result: Dict[str, Optional[str]] = {
        "typeCheck": f"{prefix} {type_check_name}" if type_check_name else None,
        "test": f"{prefix} test" if "test" in scripts else None,
        "lint": f"{prefix} lint" if "lint" in scripts else None,
    }
    return result if any(result.values()) else None


def _parse_target_names(text: str) -> List[str]:
    """Return target/recipe names defined at column 0 of a line.

    Matches Makefile targets (``name:``) and simple justfile recipes
    (``name:``), while a leading tab (a Makefile recipe body) or a
    ``:=`` variable assignment never matches.
    """
    names = []
    for line in text.splitlines():
        m = TARGET_NAME_RE.match(line)
        if m:
            names.append(m.group(1))
    return names


def _detect_commands_from_makefile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "Makefile")
    if not os.path.isfile(path):
        return None
    try:
        targets = set(_parse_target_names(read_text_tolerant(path)))
    except (OSError, ValueError):
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in targets), None)
    result = {
        "typeCheck": f"make {type_check_name}" if type_check_name else None,
        "test": "make test" if "test" in targets else None,
        "lint": "make lint" if "lint" in targets else None,
    }
    return result if any(result.values()) else None


def _detect_commands_from_justfile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = None
    for name in ("justfile", "Justfile"):
        candidate = os.path.join(cwd, name)
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        return None
    try:
        recipes = set(_parse_target_names(read_text_tolerant(path)))
    except (OSError, ValueError):
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in recipes), None)
    result = {
        "typeCheck": f"just {type_check_name}" if type_check_name else None,
        "test": "just test" if "test" in recipes else None,
        "lint": "just lint" if "lint" in recipes else None,
    }
    return result if any(result.values()) else None


def detect_commands(cwd: str) -> Dict[str, Optional[str]]:
    """Detect typeCheck/test/lint commands: package.json, else Makefile, else justfile.

    The first source that yields at least one command wins outright
    (architecture.md §5's "else" chain is a whole-strategy fallback,
    not a per-field merge across sources).
    """
    for detector in (
        _detect_commands_from_package_json,
        _detect_commands_from_makefile,
        _detect_commands_from_justfile,
    ):
        found = detector(cwd)
        if found:
            found = dict(found)
            found["source"] = "detected"
            return found
    return {"typeCheck": None, "test": None, "lint": None, "source": "none"}


def resolve_commands(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Dict[str, Optional[str]]:
    """Config wins outright when it declares a commands object; else detect.

    A "commands" key present but not an object warns and is treated as
    absent, falling through to detection. An unknown key inside a valid
    commands object warns without changing what is returned.
    """
    if isinstance(config, dict) and "commands" in config and config["commands"] is not None:
        raw = config["commands"]
        if isinstance(raw, dict):
            unknown = sorted(k for k in raw.keys() if k not in KNOWN_COMMANDS_KEYS)
            for key in unknown:
                warnings.append(f"unknown commands key: {key}")
            return {
                "typeCheck": raw.get("typeCheck"),
                "test": raw.get("test"),
                "lint": raw.get("lint"),
                "source": "config",
            }
        warnings.append("commands is not an object; using detection")
    return detect_commands(cwd)


def resolve_docs_home(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Tuple[Optional[str], str]:
    """Config's docsHome wins when it is a string that stays inside the
    project; else fall through to detection.

    A wrong type or an escaping path warns and is treated as absent, so
    resolution still falls through to detection rather than trusting a
    value nobody meant to configure. A configured folder that does not
    exist yet is warned about and still returned: the config is the
    project's choice, and the mode that writes there creates it only on
    the user's say-so (render_outcome.py --create-docs-home). A loaded
    config that pins no docsHome, in a project where detection finds no
    docs folder either, is warned about too: every later ``new`` would
    ask where docs live until someone sets it.
    """
    if isinstance(config, dict) and "docsHome" in config and config["docsHome"] is not None:
        value = config["docsHome"]
        if not isinstance(value, str):
            warnings.append("docsHome is not a string; using detection")
        elif _path_escapes(value):
            warnings.append("path escapes the project: docsHome")
        elif value:
            value = _normalise_slashes(value, "docsHome", warnings)
            if not os.path.isdir(os.path.join(cwd, value)):
                warnings.append(f"docsHome does not exist: {value}")
            return value, "config"
    detected = detect_docs_home(cwd)
    if detected is not None:
        return detected, "detected"
    if isinstance(config, dict):
        warnings.append(
            "docsHome is null: no docs folder detected; set docsHome in the config "
            "or run /promise adopt --docs-home <dir>"
        )
    return None, "none"


def resolve_plans_folder(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Optional[str]:
    """Config's plansFolder wins when it is a string that stays inside the
    project; else fall through to detection, on the same terms as docsHome."""
    if isinstance(config, dict) and "plansFolder" in config and config["plansFolder"] is not None:
        value = config["plansFolder"]
        if not isinstance(value, str):
            warnings.append("plansFolder is not a string; using detection")
        elif _path_escapes(value):
            warnings.append("path escapes the project: plansFolder")
        elif value:
            return _normalise_slashes(value, "plansFolder", warnings)
    return detect_plans_folder(cwd)


def resolve_framework_path(
    cwd: str, config: Optional[dict], skill_dir: str, warnings: List[str]
) -> Tuple[str, str]:
    """The project's own framework copy wins when config names one, the
    path stays inside the project, and the file exists there; else the
    bundled copy. Each way a configured path is rejected — wrong type, an
    escaping path, a file that is not there — warns and falls back to the
    bundled copy rather than raising.
    """
    bundled = (os.path.join(skill_dir, "outcome-framework.md"), "bundled")
    if isinstance(config, dict) and "frameworkPath" in config and config["frameworkPath"] is not None:
        candidate = config["frameworkPath"]
        if not isinstance(candidate, str):
            warnings.append("frameworkPath is not a string; using the bundled framework")
            return bundled
        if _path_escapes(candidate):
            warnings.append("path escapes the project: frameworkPath")
            return bundled
        if candidate:
            candidate = _normalise_slashes(candidate, "frameworkPath", warnings)
            abs_candidate = os.path.join(cwd, candidate)
            if os.path.isfile(abs_candidate):
                return os.path.abspath(abs_candidate), "project"
            warnings.append(
                f"frameworkPath does not exist: {candidate}; using the bundled framework"
            )
    return bundled


def resolve_map(
    config: Optional[dict], warnings: List[str], cwd: Optional[str] = None
) -> Tuple[Optional[dict], bool]:
    """Normalise config["map"]: unknown keys warn, "lanes" is checked for
    being an object of strings, "rowIdPattern" is checked for compiling,
    "checks" for being an array of strings, "issueTracker" for its three
    string fields, and the return says whether the map is usable.

    A "map" present but not an object warns and is treated as absent —
    there is no detection fallback for a map the way there is for
    docsHome or commands, so the value is simply null. A map that is an
    object keeps that object verbatim either way: a project can configure
    part of a map and still see what it wrote. "mapUsable" is true only
    when recipe, find, row and lanes are all present with the right
    shape; false when the map is absent or any of those four is missing
    or the wrong type, alongside a warning naming what is missing.

    When ``cwd`` is given, "recipe" and "index" are also checked on disk:
    a path that escapes the project or does not exist is warned about.
    Neither changes mapUsable — that stays a shape check, so the map a
    project configured is the map every script sees — and the map object
    is returned verbatim, backslashes included.
    """
    if not isinstance(config, dict) or "map" not in config or config["map"] is None:
        return None, False

    raw_map = config["map"]
    if not isinstance(raw_map, dict):
        warnings.append("map is not an object; treating as absent")
        return None, False

    unknown = sorted(k for k in raw_map.keys() if k not in KNOWN_MAP_KEYS)
    for key in unknown:
        warnings.append(f"unknown map key: {key}")

    lanes = raw_map.get("lanes")
    lanes_ok = isinstance(lanes, dict) and all(isinstance(v, str) for v in lanes.values())
    if "lanes" in raw_map and not lanes_ok:
        warnings.append("map.lanes is not an object of strings")

    missing = [key for key in MAP_STRING_KEYS if not isinstance(raw_map.get(key), str)]
    if not lanes_ok:
        missing.append("lanes")

    usable = not missing
    if not usable:
        warnings.append(f"map incomplete: missing {', '.join(missing)}")

    row_id_pattern = raw_map.get("rowIdPattern")
    if isinstance(row_id_pattern, str):
        try:
            re.compile(row_id_pattern)
        except re.error as exc:
            warnings.append(f"map.rowIdPattern does not compile: {row_id_pattern!r}: {exc}")

    checks = raw_map.get("checks")
    if "checks" in raw_map and not (
        isinstance(checks, list) and all(isinstance(c, str) for c in checks)
    ):
        warnings.append("map.checks is not an array of strings")

    tracker = raw_map.get("issueTracker")
    if "issueTracker" in raw_map and not (
        isinstance(tracker, dict)
        and all(isinstance(tracker.get(k), str) for k in ISSUE_TRACKER_KEYS)
    ):
        warnings.append(
            "map.issueTracker is not an object with string kind, repo, template"
        )

    if cwd is not None:
        for key in MAP_FILE_KEYS:
            rel = raw_map.get(key)
            if not isinstance(rel, str) or not rel:
                continue
            if _path_escapes(rel):
                warnings.append(f"path escapes the project: map.{key}")
                continue
            if "\\" in rel:
                warnings.append(f"map.{key} uses backslashes; use forward slashes: {rel!r}")
                rel = rel.replace("\\", "/")
            if not os.path.isfile(os.path.join(cwd, rel)):
                warnings.append(f"map.{key} does not exist: {rel}")

    return raw_map, usable


def detect_claude_md(cwd: str) -> Dict[str, Any]:
    """CLAUDE.md at the project root, else .claude/CLAUDE.md, else absent."""
    for candidate in (
        os.path.join(cwd, "CLAUDE.md"),
        os.path.join(cwd, ".claude", "CLAUDE.md"),
    ):
        if os.path.isfile(candidate):
            try:
                text = read_text_tolerant(candidate)
            except (OSError, ValueError):
                text = ""
            return {
                "path": os.path.abspath(candidate),
                "hasPromiseSection": PROMISE_BEGIN_MARKER in text,
            }
    return {"path": None, "hasPromiseSection": False}


def scan_existing_docs(
    cwd: str, docs_home: Optional[str], warnings: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """Every *.md under docsHome, one level deep -- the folder and its
    immediate subdirectories, the same scan lint_outcome.py and
    outcome_rows.py --search use -- whose §0 TLDR heading sits outside any
    fenced code block.

    Headings inside a ``` / ~~~ fence are illustrations, not structure,
    so a framework copy or a doc quoting the template is not listed as
    an outcome doc, and the title/status/date lookups skip fenced text
    too. A file that cannot be read or is not UTF-8 is skipped with a
    warning when a warnings list is given; a subdirectory that cannot be
    listed is skipped the same way.
    """
    if not docs_home:
        return []
    docs_dir = os.path.join(cwd, docs_home)
    if not os.path.isdir(docs_dir):
        return []
    candidates: List[Tuple[str, str]] = []  # (relative path under docsHome, absolute path)
    for name in sorted(os.listdir(docs_dir)):
        full = os.path.join(docs_dir, name)
        if os.path.isfile(full) and name.endswith(".md"):
            candidates.append((name, full))
        elif os.path.isdir(full):
            try:
                inner = sorted(os.listdir(full))
            except OSError as exc:
                if warnings is not None:
                    warnings.append(f"skipped unreadable folder {docs_home}/{name}: {exc}")
                continue
            for name2 in inner:
                full2 = os.path.join(full, name2)
                if os.path.isfile(full2) and name2.endswith(".md"):
                    candidates.append((f"{name}/{name2}", full2))
    results = []
    for name, full in candidates:
        try:
            text = read_text_tolerant(full)
        except (OSError, ValueError) as exc:
            if warnings is not None:
                warnings.append(f"skipped unreadable doc {docs_home}/{name}: {exc}")
            continue
        lines = unfenced(text.splitlines())
        if not any(line.startswith(TLDR_HEADING) for line in lines):
            continue
        title = None
        status = None
        last_decision = None
        for line in lines:
            if title is None:
                m = H1_RE.match(line)
                if m:
                    title = m.group(1)
            if status is None:
                m = STATUS_RE.match(line)
                if m:
                    status = m.group(1)
            if last_decision is None:
                m = LAST_DECISION_RE.search(line)
                if m:
                    last_decision = m.group(1)
        results.append(
            {
                "path": "/".join([docs_home, name]),
                "title": title,
                "status": status,
                "lastDecision": last_decision,
            }
        )
    return sorted(results, key=lambda d: d["path"])


def _first_word(text: str) -> str:
    """The input's first whitespace-delimited token, lower-cased and unpunctuated."""
    stripped = text.strip()
    if not stripped:
        return ""
    token = stripped.split(None, 1)[0]
    return token.strip(_MODE_WORD_PUNCT).lower()


def _doc_basename_stem(doc: Dict[str, Any]) -> str:
    """A doc's path basename with a trailing .md removed, for substring matching."""
    path = doc.get("path") or ""
    name = os.path.basename(path)
    if name.lower().endswith(".md"):
        name = name[: -len(".md")]
    return name


def _matching_docs(text_lower: str, existing_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """existingDocs whose path basename (sans .md) or title is a substring of the input."""
    matches = []
    for doc in existing_docs:
        basename = _doc_basename_stem(doc).lower()
        title = (doc.get("title") or "").lower()
        if (basename and basename in text_lower) or (title and title in text_lower):
            matches.append(doc)
    return matches


def _doc_label(doc: Dict[str, Any]) -> str:
    """The name to show for a doc in a signal: its title, else its basename."""
    return doc.get("title") or _doc_basename_stem(doc)


def _near(text_lower: str, re_a: re.Pattern[str], re_b: re.Pattern[str], window_chars: int = 30) -> bool:
    """True when some re_a match and some re_b match sit within window_chars of each other."""
    a_spans = [m.span() for m in re_a.finditer(text_lower)]
    if not a_spans:
        return False
    b_spans = [m.span() for m in re_b.finditer(text_lower)]
    if not b_spans:
        return False
    for a_start, a_end in a_spans:
        for b_start, b_end in b_spans:
            gap = max(a_start, b_start) - min(a_end, b_end)
            if gap <= window_chars:
                return True
    return False


def suggest_mode(
    input_text: str,
    existing_docs: List[Dict[str, Any]],
    map_value: Optional[dict],
) -> Tuple[Optional[str], List[str], List[str], bool]:
    """A mode hint for the --input text (architecture.md §4's dispatch table).

    A recognised first word wins outright and skips every check below it —
    there is nothing left to be ambiguous with. Otherwise each remaining
    rule is checked, in the table's own priority order, against the same
    input, and the highest-priority match is the suggestion. Returns
    (suggestedMode, signals, extraWarnings, ambiguous) — extraWarnings
    folds into the caller's own warnings[] (currently only a bad
    map.rowIdPattern); ambiguous is true only when a lower-priority rule
    also matched with a different mode, in which case that rule's own
    signal is appended too. This never raises: an input that trips
    nothing falls through to the default, because this is a hint for the
    router, not a second router that could itself be "wrong".
    """
    text = input_text or ""
    text_lower = text.lower()
    extra_warnings: List[str] = []

    # A recognised first word wins outright and skips inference entirely.
    first = _first_word(text)
    if first in RECOGNISED_MODES:
        return first, ["first word is a mode name"], extra_warnings, False

    matches = _matching_docs(text_lower, existing_docs)
    candidates: List[Tuple[str, List[str]]] = []

    # Existing-doc match: at most one outcome from this block — each case
    # refines the same matches/status, not an independent signal.
    if matches and CRITIQUE_VERB_RE.search(text):
        label = _doc_label(matches[0])
        candidates.append(("review", [f"matches existing doc {label!r} + critique verb"]))
    elif len(matches) >= 2:
        candidates.append(("merge", [f"matches {len(matches)} distinct existing docs"]))
    elif len(matches) == 1:
        doc = matches[0]
        status = (doc.get("status") or "").lower()
        label = _doc_label(doc)
        if status == "agreed" and ARM_PHRASE_RE.search(text):
            candidates.append(("arm", [f"matches existing doc {label!r} (agreed) + arm phrase"]))
        else:
            candidates.append(("revise", [f"matches existing doc {label!r}"]))
    elif existing_docs and GENERIC_CHANGE_VERB_RE.search(text) and DOC_REFERENCE_WORD_RE.search(text):
        # A generic change verb aimed at "the doc"/"the outcome", no title
        # named: which doc is ambiguous, the mode is not — at least one
        # outcome doc exists, so this can only be a change to it.
        signal = ['generic change verb + "doc"']
        if len(existing_docs) > 1:
            signal.append("ambiguous: which doc")
        candidates.append(("revise", signal))

    # Reconcile: a commit sha, a feat/fix branch or a test-file path stand
    # alone. A bare ticket number needs an accompanying shipped/landed/PR
    # word; failing that, a shipped/landed phrase on its own still counts.
    m = RECONCILE_STRONG_PATTERN_RE.search(text)
    if m:
        candidates.append(
            ("reconcile", [f"matches a PR/commit/branch/test-file pattern: {m.group(0)!r}"])
        )
    else:
        ticket = TICKET_NUMBER_RE.search(text)
        if ticket and RECONCILE_ACCOMPANY_RE.search(text):
            candidates.append(
                (
                    "reconcile",
                    [f"matches a PR/commit/branch/test-file pattern: {ticket.group(0)!r}"],
                )
            )
        else:
            m = RECONCILE_PHRASE_RE.search(text)
            if m:
                candidates.append(
                    ("reconcile", [f"matches a shipped/landed phrase: {m.group(0)!r}"])
                )

    # Intake: the input names a row id shaped by the project's own map.
    if isinstance(map_value, dict) and map_value.get("rowIdPattern"):
        pattern_text = map_value["rowIdPattern"]
        try:
            row_id_re = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            extra_warnings.append(f"bad map.rowIdPattern {pattern_text!r}: {exc}; skipping rule 7")
        else:
            for token in ROW_ID_TOKEN_RE.findall(text):
                candidate_token = token.strip(_MODE_WORD_PUNCT)
                if candidate_token and row_id_re.fullmatch(candidate_token):
                    candidates.append(
                        ("intake", [f"token {candidate_token!r} matches map.rowIdPattern"])
                    )
                    break

    # Intake: a list shape, or feedback vocabulary.
    list_item_count = sum(1 for line in text.splitlines() if LIST_ITEM_RE.match(line))
    if list_item_count >= 3:
        candidates.append(("intake", [f"{list_item_count} list items (>= 3)"]))
    else:
        m = INTAKE_WORD_RE.search(text)
        if m:
            candidates.append(("intake", [f"contains intake word {m.group(0)!r}"]))

    # Review: a critique verb with no existing-doc match — pasted or
    # external content, not a request about a doc already on file. A bare
    # "feedback" is deliberately not one of these verbs (see
    # REVIEW_NO_DOC_VERB_RE): it has already had its chance to read as
    # intake above, and a plain mention leans there.
    if not matches:
        m = REVIEW_NO_DOC_VERB_RE.search(text)
        if m:
            candidates.append(
                ("review", [f"critique verb {m.group(0)!r}, no doc match (external content)"])
            )

    # Adopt: the literal CLAUDE.md, an install/setup verb near "promise",
    # or an install/setup verb aimed at this project without the word
    # "promise" ever appearing.
    if "claude.md" in text_lower:
        candidates.append(("adopt", ["contains 'CLAUDE.md'"]))
    elif _near(text_lower, ADOPT_TRIGGER_RE, PROMISE_WORD_RE):
        candidates.append(("adopt", ["adopt trigger word near 'promise'"]))
    elif ADOPT_TRIGGER_RE.search(text_lower) and ADOPT_LOCAL_RE.search(text_lower):
        candidates.append(("adopt", ["adopt trigger word + local project reference"]))

    if not candidates:
        # A bare ticket number, alone, is not a signal for any mode above
        # — say it was seen rather than claiming nothing stood out at all.
        if TICKET_NUMBER_RE.search(text) and not RECONCILE_ACCOMPANY_RE.search(text):
            return "new", ["ticket reference"], extra_warnings, False
        return "new", ["no stronger signal; default"], extra_warnings, False

    winner_mode, winner_signals = candidates[0]
    signals = list(winner_signals)
    ambiguous = False
    for mode, sig in candidates[1:]:
        if mode != winner_mode:
            ambiguous = True
            signals.extend(sig)
    return winner_mode, signals, extra_warnings, ambiguous


def build_orientation(
    mode_arg: Optional[str], cwd_arg: Optional[str], input_arg: Optional[str] = None
) -> Dict[str, Any]:
    warnings: List[str] = []
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()
    mode = _mode_word(mode_arg)

    try:
        raw_config, config_path, config_warnings = load_config(cwd)
    except Exception as exc:  # pragma: no cover - defensive, never fail hard
        raw_config, config_path, config_warnings = None, None, [f"config detection failed: {exc}"]
    warnings.extend(config_warnings)

    try:
        docs_home, docs_home_source = resolve_docs_home(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        docs_home, docs_home_source = None, "none"
        warnings.append(f"docsHome detection failed: {exc}")

    try:
        plans_folder = resolve_plans_folder(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        plans_folder = None
        warnings.append(f"plansFolder detection failed: {exc}")

    try:
        commands = resolve_commands(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        commands = {"typeCheck": None, "test": None, "lint": None, "source": "none"}
        warnings.append(f"commands detection failed: {exc}")

    try:
        framework_path, framework_source = resolve_framework_path(
            cwd, raw_config, skill_dir, warnings
        )
    except Exception as exc:  # pragma: no cover
        framework_path = os.path.join(skill_dir, "outcome-framework.md")
        framework_source = "bundled"
        warnings.append(f"frameworkPath resolution failed: {exc}")

    try:
        map_value, map_usable = resolve_map(raw_config, warnings, cwd)
    except Exception as exc:  # pragma: no cover
        map_value, map_usable = None, False
        warnings.append(f"map resolution failed: {exc}")

    try:
        claude_md = detect_claude_md(cwd)
    except Exception as exc:  # pragma: no cover
        claude_md = {"path": None, "hasPromiseSection": False}
        warnings.append(f"claudeMd detection failed: {exc}")

    try:
        existing_docs = scan_existing_docs(cwd, docs_home, warnings)
    except Exception as exc:  # pragma: no cover
        existing_docs = []
        warnings.append(f"existingDocs scan failed: {exc}")

    config_loaded = raw_config is not None
    adopted = bool(config_loaded and claude_md.get("hasPromiseSection"))
    if not adopted:
        warnings.append("project not adopted — run /promise adopt")

    suggested_mode: Optional[str] = None
    signals: List[str] = []
    ambiguous = False
    if input_arg is not None:
        try:
            suggested_mode, signals, suggest_warnings, ambiguous = suggest_mode(
                input_arg, existing_docs, map_value
            )
            warnings.extend(suggest_warnings)
        except Exception as exc:  # pragma: no cover - defensive, never fail hard
            suggested_mode, signals, ambiguous = None, [], False
            warnings.append(f"mode suggestion failed: {exc}")

    return {
        "skillDir": skill_dir,
        "cwd": cwd,
        "mode": mode,
        "frameworkPath": framework_path,
        "frameworkSource": framework_source,
        "config": {
            "path": config_path,
            "loaded": config_loaded,
            "raw": raw_config if config_loaded else {},
        },
        "docsHome": docs_home,
        "docsHomeSource": docs_home_source,
        "plansFolder": plans_folder,
        "commands": commands,
        "map": map_value,
        "mapUsable": map_usable,
        "claudeMd": claude_md,
        "adopted": adopted,
        "existingDocs": existing_docs,
        "suggestedMode": suggested_mode,
        "signals": signals,
        "ambiguous": ambiguous,
        "warnings": warnings,
    }


def _mode_word(mode_arg: Optional[str]) -> Optional[str]:
    """The "mode" value: the recognised word, "infer" for an unrecognised
    one, null when no --mode was passed."""
    if not mode_arg:
        return None
    if mode_arg in RECOGNISED_MODES:
        return mode_arg
    return "infer"


def _fallback_result(mode_arg: Optional[str], cwd_arg: Optional[str], error: Exception) -> Dict[str, Any]:
    """Absolute last resort so the process can still print a valid, complete schema."""
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()
    return {
        "skillDir": skill_dir,
        "cwd": cwd,
        "mode": _mode_word(mode_arg),
        "frameworkPath": os.path.join(skill_dir, "outcome-framework.md"),
        "frameworkSource": "bundled",
        "config": {"path": None, "loaded": False, "raw": {}},
        "docsHome": None,
        "docsHomeSource": "none",
        "plansFolder": None,
        "commands": {"typeCheck": None, "test": None, "lint": None, "source": "none"},
        "map": None,
        "mapUsable": False,
        "claudeMd": {"path": None, "hasPromiseSection": False},
        "adopted": False,
        "existingDocs": [],
        "suggestedMode": None,
        "signals": [],
        "ambiguous": False,
        "warnings": [f"orient.py internal error: {error}", "project not adopted — run /promise adopt"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orient.py",
        description=(
            "Resolve promise skill Phase 0 orientation (framework, config, "
            "docs home, commands, existing docs, CLAUDE.md adoption) and "
            "print it as one JSON object. Exits 0 for any valid invocation; "
            "a usage error (an unrecognised flag), a --cwd that is not a "
            "directory, or an --input-file that cannot be read exits 2."
        ),
    )
    parser.add_argument(
        "--mode", default=None,
        help="the mode word the skill was invoked with; without it the JSON says \"mode\": null",
    )
    parser.add_argument(
        "--cwd", default=None, help="project root to orient against (default: current directory)"
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "the user's full argument string; when given, the JSON gains "
            "suggestedMode, signals and ambiguous (a router hint, "
            "architecture.md §4)"
        ),
    )
    parser.add_argument(
        "--input-file",
        default=None,
        help="read the user's message from this file ('-' for stdin) instead of --input; "
             "use it whenever the message may contain quotes, so it never passes through a shell",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if args.cwd is not None and not os.path.isdir(args.cwd):
        print(f"orient.py: no such directory: {args.cwd}", file=sys.stderr)
        return 2

    if getattr(args, "input_file", None):
        try:
            if args.input_file == "-":
                args.input = sys.stdin.read()
            else:
                with open(args.input_file, "r", encoding="utf-8-sig") as fh:
                    args.input = fh.read()
        except UnicodeDecodeError as exc:
            print(f"orient.py: --input-file is not UTF-8: {exc}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"orient.py: cannot read --input-file: {exc}", file=sys.stderr)
            return 2

    try:
        result = build_orientation(args.mode, args.cwd, args.input)
    except Exception as exc:  # pragma: no cover - absolute last resort
        result = _fallback_result(args.mode, args.cwd, exc)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
