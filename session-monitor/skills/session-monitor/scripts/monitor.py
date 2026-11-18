#!/usr/bin/env python3
"""Bounded local session evidence. No raw transcript material leaves this process."""
import argparse
import collections
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile

VERSION = 1
MAX_RECORD = 256 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_FILES = 64
MAX_DISCOVERY_ENTRIES = 4096
MARKER = "session-monitor-v1\n"
DEFAULT_STATE = Path.home() / ".local/state/session-monitor"
EXPLANATIONS = {
    "tool_call": "A tool invocation was observed; outcome is separate.",
    "tool_failure": "Tool returned an explicit error or non-zero exit.",
    "tool_failure_reported": "Tool output mentions a non-zero exit; inspect locally before treating as a new failure.",
    "hook_error": "Structured hook or hook-targeted runtime error; inspect locally.",
    "hook_error_reported": "Tool output reports a hook-style error; root cause unverified.",
    "policy_refusal": "A claim, permission or merge gate refused an action.",
    "review_limit": "Review-round limit stopped further review.",
    "billing_block": "Account billing or spending prevented CI from starting.",
    "intentional_interruption": "Harness recorded a turn interruption, not a hook failure.",
}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def discover_codex(root, days, now=None):
    """Bounded date-tree discovery by activity time, including older still-active sessions."""
    cutoff = (now if now is not None else dt.datetime.now().timestamp()) - days * 86400
    stats = {"entries_examined": 0, "entry_cap": MAX_DISCOVERY_ENTRIES, "capped": False, "unavailable_directories": 0}
    found = []
    def visit(folder, depth):
        entries = []
        try:
            with os.scandir(folder) as source:
                for entry in source:
                    if stats["entries_examined"] >= MAX_DISCOVERY_ENTRIES:
                        stats["capped"] = True
                        break
                    stats["entries_examined"] += 1
                    if depth < 3:
                        pattern = r"[0-9]{4}" if depth == 0 else r"[0-9]{2}"
                        if re.fullmatch(pattern, entry.name) and entry.is_dir(follow_symlinks=False):
                            entries.append(entry)
                    elif entry.name.endswith(".jsonl") and entry.is_file(follow_symlinks=False):
                        info = entry.stat(follow_symlinks=False)
                        if info.st_mtime >= cutoff:
                            found.append((info.st_mtime, Path(entry.path)))
        except OSError:
            stats["unavailable_directories"] += 1
            return
        # Recent date folders first, but never assume their date equals last activity.
        for entry in sorted(entries, key=lambda item: item.name, reverse=True):
            if stats["entries_examined"] >= MAX_DISCOVERY_ENTRIES:
                stats["capped"] = True
                break
            visit(Path(entry.path), depth + 1)
    if root.is_symlink():
        stats["unavailable_directories"] += 1
    else:
        visit(root, 0)
    found.sort(key=lambda item: (-item[0], str(item[1])))
    stats["matching_files"] = len(found)
    return [path for _, path in found], stats


def checked(path, directory=False):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError("symlink or non-owned path refused")
    if directory != stat.S_ISDIR(info.st_mode) or (not directory and not stat.S_ISREG(info.st_mode)):
        raise ValueError("unexpected path type refused")
    return info


def private_root(root, create=False):
    if not root.exists():
        if not create:
            raise ValueError("monitor state directory does not exist")
        root.mkdir(mode=0o700, parents=True)
        marker = root / ".session-monitor-owner"
        with marker.open("x") as out:
            out.write(MARKER)
        marker.chmod(0o600)
    checked(root, True)
    marker = root / ".session-monitor-owner"
    checked(marker)
    if marker.read_text() != MARKER:
        raise ValueError("directory is not monitor-owned")


def atomic(root, name, value):
    target = root / name
    if target.exists() or target.is_symlink():
        checked(target)
    fd, temporary = tempfile.mkstemp(prefix=".write-", dir=root)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value, out, sort_keys=True, indent=2)
            out.write("\n")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def lock(root):
    path = root / "lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        checked(path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another monitor run holds the lock") from None
        yield
    finally:
        os.close(fd)


def state_read(root):
    path = root / "state.json"
    if not path.exists():
        return {"v": VERSION, "sources": {}}
    checked(path)
    if path.stat().st_size > 1 << 20:
        raise ValueError("checkpoint too large; inspect repair plan")
    try:
        value = json.loads(path.read_text())
        if value.get("v") != VERSION or not isinstance(value["sources"], dict):
            raise ValueError()
        for source, cursor in value["sources"].items():
            if not re.fullmatch(r"[a-f0-9]{24}", source) or not isinstance(cursor, dict):
                raise ValueError()
            for field in ("offset", "dev", "ino"):
                if type(cursor.get(field)) is not int or cursor[field] < 0:
                    raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError("checkpoint corrupt; inspect reset-checkpoint repair plan") from None
    return value


def categories(text, error=False, hook=False):
    found = set()
    if error:
        found.add("tool_failure")
    elif re.search(r"(?:Process exited with code|Process exit code:|exit_code(?:\\?[\"'])?\s*[:=])\s*[1-9][0-9]*", text):
        found.add("tool_failure_reported")
    if re.search(r"\brefused\b|\bpermission denied\b|only a person ends that wait|pre-merge[^\n]{0,40}\bNO\b", text, re.I):
        found.add("policy_refusal")
    if re.search(r"review-round stop|review rounds?[^\n]{0,30}\bcap\b", text, re.I):
        found.add("review_limit")
    if "job was not started" in text and re.search(r"payments have failed|spending limit", text, re.I):
        found.add("billing_block")
    if hook and re.search(r"error|fail|non.?zero|exit(?:ed)?(?: with)? (?:code )?[1-9]", text, re.I):
        found.add("hook_error")
    elif re.search(r"(?m)^(?:PreToolUse|PostToolUse|SessionStart|SessionEnd|Stop|UserPromptSubmit) hook[^\n]{0,100}(?:error|failed)", text, re.I):
        found.add("hook_error_reported")
    return found


def classify(value):
    if not isinstance(value, dict):
        return set()
    payload = value.get("payload", value)
    if not isinstance(payload, dict):
        return set()
    kind = payload.get("type")
    if kind in {"turn_aborted", "interrupted"}:
        return {"intentional_interruption"}
    if kind in {"function_call", "custom_tool_call", "tool_use"}:
        return {"tool_call"}
    if kind in {"hook_error", "hook_failed"}:
        return {"hook_error"}
    if kind in {"function_call_output", "custom_tool_call_output", "tool_result"}:
        output = payload.get("output", payload.get("content", ""))
        text = output if isinstance(output, str) else json.dumps(output)
        return categories(text, error=payload.get("is_error") is True)
    # Claude embeds tools in message content; ordinary chat is never classified by its words.
    message = value.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), list):
        found = set()
        for item in message["content"][:1000]:
            if isinstance(item, dict) and item.get("type") in {"tool_use", "tool_result"}:
                found.update(classify(item))
        return found
    return set()


class Scan:
    def __init__(self, state):
        self.state = state
        self.findings = []
        self.counts = collections.Counter()
        self.coverage = []
        self.warnings = collections.Counter()
        self.remaining = MAX_TOTAL

    def add(self, source, position, kinds):
        for kind in sorted(kinds):
            self.counts[kind] += 1
            if len(self.findings) < 500:
                self.findings.append({"id": digest(f"{source}:{position}:{kind}"), "source": source,
                                      "position": position, "kind": kind})
            else:
                self.warnings["finding_sample_capped"] += 1

    def jsonl(self, path):
        info = checked(path)
        source = digest(str(path.absolute()))
        previous = self.state["sources"].get(source, {})
        start = previous.get("offset", 0)
        rotated = bool(previous and (previous.get("ino") != info.st_ino or previous.get("dev") != info.st_dev or start > info.st_size))
        if rotated:
            start = 0
            self.warnings["source_rotated_or_truncated"] += 1
        limit = min(MAX_FILE, self.remaining)
        if limit <= 0:
            self.warnings["total_byte_budget_reached"] += 1
            return
        skipped = 0
        if not previous or rotated:
            skipped = max(0, info.st_size - limit)
            start = skipped
        consumed = 0
        records, unclassified = 0, 0
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError("input changed during open")
            stream.seek(start)
            dropping = bool(skipped or previous.get("dropping", False))
            cursor = start
            while consumed < limit:
                pos = stream.tell()
                line = stream.readline(min(MAX_RECORD + 1, limit - consumed))
                if not line:
                    break
                consumed += len(line)
                if not line.endswith(b"\n"):
                    if len(line) > MAX_RECORD or dropping:
                        dropping = True
                        cursor = stream.tell()
                        self.warnings["oversized_or_partial_record"] += 1
                        continue
                    stream.seek(pos)
                    self.warnings["incomplete_record_retried"] += 1
                    break
                cursor = stream.tell()
                if dropping:
                    dropping = False
                    continue
                if len(line) > MAX_RECORD:
                    self.warnings["oversized_or_partial_record"] += 1
                    continue
                try:
                    value = json.loads(line)
                except (ValueError, UnicodeError, RecursionError):
                    self.warnings["malformed_record"] += 1
                    continue
                kinds = classify(value)
                records += 1
                unclassified += not bool(kinds)
                self.add(source, pos, kinds)
        self.remaining -= consumed
        self.state["sources"][source] = {"offset": cursor, "dev": info.st_dev, "ino": info.st_ino, "dropping": dropping}
        self.coverage.append({"source": source, "bytes_read": consumed, "history_skipped_bytes": skipped,
                              "unread_bytes": max(0, info.st_size - cursor), "rotated": rotated,
                              "records_read": records, "unclassified_records": unclassified})

    def database(self, path, thread=None):
        info = checked(path)
        source = digest(str(path.absolute()) + ":thread:" + (thread or "*"))
        previous = self.state["sources"].get(source, {})
        last = previous.get("offset", 0)
        connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=1)
        try:
            connection.execute("PRAGMA query_only=ON")
            steps = [0]
            def budget():
                steps[0] += 1
                return steps[0] > 10000
            connection.set_progress_handler(budget, 1000)
            highest = connection.execute("SELECT max(id) FROM logs").fetchone()[0] or 0
            rotated = bool(previous and (previous.get("dev") != info.st_dev or previous.get("ino") != info.st_ino or highest < last))
            if rotated:
                last = 0
                self.warnings["database_rotated_or_reset"] += 1
            where = "id > ?" + (" AND thread_id = ?" if thread else "")
            args = (last, thread) if thread else (last,)
            rows = connection.execute("SELECT id,level,substr(target,1,256),substr(feedback_log_body,1,16384) FROM logs WHERE "
                                      + where + " ORDER BY id DESC LIMIT 2001", args).fetchall()
            capped = len(rows) > 2000
            for pos, level, target, body in reversed(rows[:2000]):
                self.add(source, pos, categories(body or "", hook="hook" in (target or "").lower() and level.upper() in {"ERROR", "WARN"}))
            self.state["sources"][source] = {"offset": rows[0][0] if rows else last, "dev": info.st_dev, "ino": info.st_ino}
            self.coverage.append({"source": source, "rows_read": min(2000, len(rows)), "older_rows_skipped": capped,
                                  "rotated": rotated})
        finally:
            connection.close()

    def report(self):
        return {"v": VERSION, "counts": dict(self.counts), "findings": self.findings, "coverage": self.coverage,
                "warnings": dict(self.warnings), "explanations": {k: EXPLANATIONS[k] for k in self.counts},
                "hook_cause": "unverified; inspect referenced local evidence before repair"}


def repair(root, action, apply=False, expect=None):
    private_root(root)
    names = ("state.json", "latest.json", ".session-monitor-owner")
    for name in names:
        path = root / name
        if path.exists() or path.is_symlink():
            checked(path)
    def fingerprint():
        value = hashlib.sha256((str(root.absolute()) + action).encode())
        for name in names:
            path = root / name
            if path.exists() or path.is_symlink():
                info = checked(path)
                if info.st_size > 1 << 20:
                    raise ValueError("monitor file too large for repair")
                value.update(name.encode() + str((info.st_ino, info.st_mode, info.st_size)).encode() + path.read_bytes())
        return value.hexdigest()
    guard = fingerprint()
    plan = {"action": action, "applied": False, "expect": guard,
            "scope": "monitor-owned checkpoint and fixed output files only"}
    if not apply:
        return plan
    with lock(root):
        if not expect or fingerprint() != expect:
            raise ValueError("repair plan stale or missing; use the current plan expect hash")
        if action == "reset-checkpoint":
            source, backup = root / "state.json", root / "state.before-reset.json"
            if backup.exists() or backup.is_symlink():
                raise ValueError("existing checkpoint backup must be inspected first")
            checked(source)
            os.replace(source, backup)
            backup.chmod(0o600)
        else:
            root.chmod(0o700)
            for name in (*names, "lock"):
                if (root / name).exists():
                    (root / name).chmod(0o600)
        plan["applied"] = True
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--input", nargs="+", default=[])
    scan.add_argument("--codex-days", type=int, choices=range(1, 8))
    scan.add_argument("--sqlite", type=Path)
    scan.add_argument("--thread")
    scan.add_argument("--daily", action="store_true")
    for command in (scan, sub.add_parser("repair")):
        command.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    fix = sub.choices["repair"]
    fix.add_argument("--action", choices=("reset-checkpoint", "tighten-permissions"), required=True)
    fix.add_argument("--apply", action="store_true")
    fix.add_argument("--expect")
    args = parser.parse_args(argv)
    try:
        if args.command == "repair":
            print(json.dumps(repair(args.state_dir, args.action, args.apply, args.expect), indent=2))
            return 0
        paths = [Path(p).expanduser().absolute() for p in args.input]
        discovery = None
        if args.codex_days:
            recent, discovery = discover_codex(Path.home() / ".codex/sessions", args.codex_days)
            paths.extend(recent)
        if not paths and not args.sqlite:
            raise ValueError("choose input files, recent Codex days or a log database")
        paths = list(dict.fromkeys(paths))
        def run(state):
            worker = Scan(state)
            if len(paths) > MAX_FILES or (discovery and discovery["capped"]):
                worker.warnings["file_discovery_capped"] += 1
            if discovery and discovery["unavailable_directories"]:
                worker.warnings["discovery_directory_unavailable"] += discovery["unavailable_directories"]
            for path in paths[:MAX_FILES]:
                try:
                    worker.jsonl(path)
                except (OSError, ValueError):
                    worker.warnings["input_unavailable_or_refused"] += 1
            if args.sqlite:
                try:
                    worker.database(args.sqlite, args.thread)
                except (OSError, ValueError, sqlite3.Error):
                    worker.warnings["database_unavailable_or_budget_reached"] += 1
            report = worker.report()
            if discovery is not None:
                report["discovery"] = discovery
            return report
        if args.daily:
            private_root(args.state_dir, create=True)
            with lock(args.state_dir):
                state = state_read(args.state_dir)
                report = run(state)
                # Bound long-lived checkpoint growth; do not silently forget old cursors.
                if len(state["sources"]) > 2048:
                    raise ValueError("checkpoint source cap reached; inspect before reset")
                atomic(args.state_dir, "latest.json", report)
                atomic(args.state_dir, "state.json", state)
        else:
            report = run({"v": VERSION, "sources": {}})
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        # Never echo OS error messages: they can contain sensitive source paths.
        print(json.dumps({"error": "monitor refused operation", "reason": str(error) if isinstance(error, ValueError) else "local IO failure"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
