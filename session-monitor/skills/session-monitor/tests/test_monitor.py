import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("monitor", Path(__file__).parents[1] / "scripts/monitor.py")
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def event(self, kind, **fields):
        return {"type": "response_item", "payload": {"type": kind, **fields}}

    def test_recent_discovery_includes_old_creation_folder_active_today(self):
        sessions = self.root / "sessions"
        old = sessions / "2026/11/17"; old.mkdir(parents=True)
        today = sessions / "2026/11/18"; today.mkdir(parents=True)
        active = old / "ongoing.jsonl"; active.write_text("{}\n")
        stale = old / "stale.jsonl"; stale.write_text("{}\n")
        current = today / "new.jsonl"; current.write_text("{}\n")
        now = 1805605200
        os.utime(active, (now, now)); os.utime(current, (now, now))
        os.utime(stale, (now - 3 * 86400, now - 3 * 86400))
        paths, coverage = m.discover_codex(sessions, 1, now=now)
        self.assertEqual(set(paths), {active, current})
        self.assertFalse(coverage["capped"])
        self.assertEqual(coverage["matching_files"], 2)

    def test_discovery_budget_is_explicit_and_does_not_follow_symlinks(self):
        sessions = self.root / "sessions"; sessions.mkdir()
        (sessions / "2026").symlink_to(self.root, target_is_directory=True)
        for n in range(10):
            (sessions / ("noise%d" % n)).touch()
        with patch.object(m, "MAX_DISCOVERY_ENTRIES", 4):
            paths, coverage = m.discover_codex(sessions, 1)
        self.assertEqual(paths, [])
        self.assertTrue(coverage["capped"])
        self.assertEqual(coverage["entries_examined"], 4)

    def file(self, events):
        path = self.root / "session.jsonl"
        path.write_text("".join(json.dumps(v) + "\n" for v in events))
        return path

    def test_real_stops_are_not_hook_faults_and_chat_is_inert(self):
        self.assertEqual(m.classify(self.event("message", role="assistant", content="PreToolUse hook failed")), set())
        expected = {
            "refused: only a person ends that wait": "policy_refusal",
            "review-round stop: two review rounds cap 2": "review_limit",
            "The job was not started because recent account payments have failed": "billing_block",
            "Process exited with code 1": "tool_failure_reported",
        }
        for text, category in expected.items():
            self.assertEqual(m.classify(self.event("function_call_output", output=text)), {category})
        self.assertEqual(m.classify(self.event("turn_aborted", reason="interrupted")), {"intentional_interruption"})
        self.assertEqual(m.classify(self.event("hook_error", message="secret")), {"hook_error"})
        self.assertEqual(m.classify(self.event("function_call_output", output="PreToolUse hook failed: secret")), {"hook_error_reported"})

    def test_claude_error_and_secret_canary_never_reach_report(self):
        canary = "piano-pond-private-value-92736"
        event = {"message": {"content": [{"type": "tool_result", "is_error": True, "content": canary}]}}
        path = self.file([event, self.event("function_call", arguments=canary)])
        scanner = m.Scan({"v": 1, "sources": {}})
        scanner.jsonl(path)
        result = json.dumps(scanner.report())
        self.assertNotIn(canary, result)
        self.assertNotIn(str(path), result)
        self.assertEqual(scanner.counts, {"tool_failure": 1, "tool_call": 1})

    def test_daily_cursor_deduplicates_and_retries_unfinished_record(self):
        path = self.file([self.event("hook_error")])
        state = {"v": 1, "sources": {}}
        first = m.Scan(state); first.jsonl(path)
        with path.open("a") as out:
            out.write('{"payload":{"type":"hook_error"}}')
        second = m.Scan(state); second.jsonl(path)
        self.assertEqual(second.counts, {})
        with path.open("a") as out:
            out.write("\n")
        third = m.Scan(state); third.jsonl(path)
        self.assertEqual(third.counts, {"hook_error": 1})
        fourth = m.Scan(state); fourth.jsonl(path)
        self.assertEqual(fourth.counts, {})

    def test_bounds_skip_oversized_records_and_keep_next_event(self):
        path = self.file([self.event("message", content="x" * 1000), self.event("hook_error")])
        scanner = m.Scan({"v": 1, "sources": {}})
        with patch.object(m, "MAX_RECORD", 100):
            scanner.jsonl(path)
        self.assertEqual(scanner.counts, {"hook_error": 1})
        self.assertGreater(scanner.warnings["oversized_or_partial_record"], 0)

    def test_sqlite_is_read_only_thread_filtered_and_deduplicated(self):
        path = self.root / "logs.sqlite"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE logs(id INTEGER PRIMARY KEY,level TEXT,target TEXT,feedback_log_body TEXT,thread_id TEXT)")
            db.executemany("INSERT INTO logs VALUES(?,?,?,?,?)", [(1,"ERROR","codex::hooks","hook failed: CANARY","a"),
                (2,"INFO","feedback_tags","hook support true","a"), (3,"ERROR","codex::hooks","hook failed","b")])
        state = {"v": 1, "sources": {}}
        first = m.Scan(state); first.database(path, "a")
        self.assertEqual(first.counts, {"hook_error": 1})
        second = m.Scan(state); second.database(path, "a")
        self.assertEqual(second.counts, {})
        other = m.Scan(state); other.database(path, "b")
        self.assertEqual(other.counts, {"hook_error": 1})
        self.assertNotIn("CANARY", json.dumps(first.report()))

    def test_default_scan_writes_nothing_and_daily_is_private(self):
        path = self.file([self.event("hook_error")]); state = self.root / "state"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(["scan", "--input", str(path), "--state-dir", str(state)]), 0)
        self.assertFalse(state.exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(["scan", "--input", str(path), "--daily", "--state-dir", str(state)]), 0)
        self.assertEqual(state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((state / "state.json").stat().st_mode & 0o777, 0o600)

    def test_sqlite_rotation_and_same_inode_rowid_reset_replay_with_warning(self):
        path = self.root / "logs.sqlite"
        def create(row):
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,level TEXT,target TEXT,feedback_log_body TEXT,thread_id TEXT)")
                db.execute("DELETE FROM logs")
                db.execute("INSERT INTO logs VALUES(?, 'ERROR', 'codex::hooks', 'hook failed', 'a')", (row,))
        state = {"v": 1, "sources": {}}
        create(10)
        first = m.Scan(state); first.database(path)
        path.rename(self.root / "old.sqlite")
        create(1)
        rotated = m.Scan(state); rotated.database(path)
        self.assertEqual(rotated.counts, {"hook_error": 1})
        self.assertEqual(rotated.warnings["database_rotated_or_reset"], 1)
        create(10)
        advanced = m.Scan(state); advanced.database(path)
        create(1)
        reset = m.Scan(state); reset.database(path)
        self.assertEqual(reset.counts, {"hook_error": 1})
        self.assertEqual(reset.warnings["database_rotated_or_reset"], 1)

    def test_repairs_need_explicit_apply_hash_and_never_touch_arbitrary_files(self):
        root = self.root / "state"; m.private_root(root, create=True)
        state = root / "state.json"; state.write_text("broken")
        plan = m.repair(root, "reset-checkpoint")
        self.assertTrue(state.exists())
        with self.assertRaises(ValueError):
            m.repair(root, "reset-checkpoint", apply=True, expect="stale")
        self.assertTrue(m.repair(root, "reset-checkpoint", apply=True, expect=plan["expect"])["applied"])
        self.assertEqual((root / "state.before-reset.json").read_text(), "broken")
        outside = self.root / "outside"; outside.write_text("preserve")
        (root / "state.json").symlink_to(outside)
        with self.assertRaises(ValueError):
            m.repair(root, "tighten-permissions", apply=True)
        self.assertEqual(outside.read_text(), "preserve")

    def test_nonowned_directory_corrupt_state_and_overlapping_run_refuse(self):
        existing = self.root / "existing"; existing.mkdir()
        with self.assertRaises((ValueError, OSError)):
            m.private_root(existing, create=True)
        root = self.root / "owned"; m.private_root(root, create=True)
        (root / "state.json").write_text("bad")
        with self.assertRaises(ValueError):
            m.state_read(root)
        with m.lock(root):
            with self.assertRaises(ValueError):
                with m.lock(root):
                    pass


if __name__ == "__main__":
    unittest.main()
