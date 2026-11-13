"""Destructive paths use disposable repos/cache files and a mocked Docker CLI only."""
import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, plugin, filename):
    path = ROOT / plugin / "skills" / plugin / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wt = load("wt_cleanup", "worktree-cleanup", "worktree_cleanup.py")
disk = load("disk_cleanup", "disk-cleanup", "disk_cleanup.py")


class Worktrees(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.remote = self.root / "origin.git"
        self.g(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.g(self.root, "init", "--initial-branch=main", str(self.repo))
        (self.repo / "hello").write_text("hello\n")
        (self.repo / ".gitignore").write_text("node_modules/\n.env\nscratch/\n")
        self.g(self.repo, "add", ".")
        self.g(self.repo, "commit", "-m", "initial")
        self.g(self.repo, "remote", "add", "origin", str(self.remote))
        self.g(self.repo, "push", "-u", "origin", "main")
        self.g(self.repo, "remote", "set-head", "origin", "main")
        self.path = self.root / "linked checkout"
        self.g(self.repo, "worktree", "add", "-b", "finished", str(self.path))
        self.active = mock.patch.object(wt, "activity_paths", return_value=set())
        self.active.start()
        self.addCleanup(self.active.stop)

    def g(self, repo, *args):
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        return subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                               "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
                              env=env, check=True, capture_output=True, text=True).stdout.strip()

    def result(self):
        ctx = wt.repo_context(self.repo, False)
        row = next(r for r in wt.worktrees(self.repo) if r["worktree"] == str(self.path))
        return wt.inspect(ctx, row, time.time() + 1, set())

    def plan(self):
        plan = wt.scan([str(self.repo)], False, 0, measure=False)
        plan["items"] = [i for i in plan["items"] if i["status"] == "REMOVE"]
        self.assertTrue(plan["items"])
        return plan

    def unique_commit(self):
        (self.path / "new").write_text("unmerged")
        self.g(self.path, "add", "new")
        self.g(self.path, "commit", "-m", "unique")

    def test_clean_integrated_checkout_removed_and_branch_preserved(self):
        plan = self.plan()
        wt.apply(plan)
        self.assertFalse(self.path.exists())
        self.g(self.repo, "show-ref", "--verify", "refs/heads/finished")
        self.assertTrue(self.repo.is_dir())

    def test_main_is_kept_even_when_invoked_from_linked_checkout(self):
        rows = wt.scan([str(self.path)], False, 0, measure=False)["items"]
        main = next(i for i in rows if i["path"] == str(self.repo))
        self.assertEqual(main["status"], "KEEP")

    def test_dirty_tracked_files_kept(self):
        (self.path / "hello").write_text("changed")
        self.assertEqual(self.result()["status"], "KEEP")

    def test_untracked_files_kept(self):
        (self.path / "new").write_text("unsaved")
        self.assertEqual(self.result()["status"], "KEEP")

    def test_ignored_secret_kept(self):
        (self.path / ".env").write_text("FAKE_SECRET=fixture")
        self.assertIn("protected ignored", self.result()["reason"])

    def test_ignored_saved_data_kept(self):
        (self.path / "scratch").mkdir()
        (self.path / "scratch/results").write_text("saved result")
        self.assertEqual(self.result()["status"], "KEEP")

    def test_build_artifacts_removed_with_checkout(self):
        (self.path / "node_modules").mkdir()
        (self.path / "node_modules/generated").write_text("rebuildable")
        wt.apply(self.plan())
        self.assertFalse(self.path.exists())

    def test_locked_checkout_kept(self):
        self.g(self.repo, "worktree", "lock", str(self.path))
        self.assertEqual(self.result()["status"], "KEEP")

    def test_in_progress_git_operation_kept(self):
        gd = Path(self.g(self.path, "rev-parse", "--absolute-git-dir"))
        (gd / "index.lock").touch()
        self.assertIn("operation", self.result()["reason"])

    def test_unmerged_commits_kept(self):
        self.unique_commit()
        self.assertEqual(self.result()["status"], "KEEP")

    def test_recent_checkout_kept(self):
        rows = wt.scan([str(self.repo)], False, 2, measure=False)["items"]
        self.assertTrue(all(i["status"] == "KEEP" for i in rows))

    def test_live_open_file_kept(self):
        ctx = wt.repo_context(self.repo, False)
        row = next(r for r in wt.worktrees(self.repo) if r["worktree"] == str(self.path))
        out = wt.inspect(ctx, row, time.time() + 1, {str(self.path / "hello")})
        self.assertIn("live process", out["reason"])

    def test_null_parser_handles_newline_in_path(self):
        weird = self.root / "line\nbreak"
        self.g(self.repo, "worktree", "add", "--detach", str(weird))
        self.assertIn(str(weird), [r["worktree"] for r in wt.worktrees(self.repo)])

    def test_stale_origin_ref_refused(self):
        (self.repo / "remotechange").write_text("new")
        self.g(self.repo, "add", ".")
        self.g(self.repo, "commit", "-m", "advance")
        self.g(self.repo, "push", "origin", "main")
        old = self.g(self.path, "rev-parse", "HEAD")
        self.g(self.repo, "update-ref", "refs/remotes/origin/main", old)
        with self.assertRaises(wt.Refused):
            wt.repo_context(self.repo, False)
        report = wt.scan([str(self.repo)], False, 0, measure=False)
        self.assertTrue(report["errors"])
        self.assertTrue(all(i["status"] == "KEEP" for i in report["items"]))

    def test_changed_head_refuses_apply(self):
        plan = self.plan()
        self.unique_commit()
        with self.assertRaises(wt.Refused):
            wt.apply(plan)
        self.assertTrue(self.path.is_dir())

    def test_full_preflight_prevents_partial_removal(self):
        other = self.root / "other"
        self.g(self.repo, "worktree", "add", "-b", "other", str(other))
        plan = self.plan()
        (other / "unsaved").write_text("keep")
        with self.assertRaises(wt.Refused):
            wt.apply(plan)
        self.assertTrue(self.path.exists())
        self.assertTrue(other.exists())

    def test_plan_digest_expiry_and_machine_binding(self):
        plan = self.plan()
        filename = self.root / "plan.json"
        digest = wt.save_plan(plan, filename)
        self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
        self.assertEqual(wt.load_plan(filename, digest), plan)
        with self.assertRaises(wt.Refused):
            wt.load_plan(filename, "0" * 64)
        plan["created"] = time.time() - 3601
        expired = self.root / "expired.json"
        digest = wt.save_plan(plan, expired)
        with self.assertRaises(wt.Refused):
            wt.load_plan(expired, digest)

    def github_result(self, prs):
        ctx = wt.repo_context(self.repo, False)
        ctx.update(github=True, slug="fixture/repo")
        row = next(r for r in wt.worktrees(self.repo) if r["worktree"] == str(self.path))
        original = wt.run

        def run(argv, *args, **kwargs):
            return json.dumps(prs) if argv[0] == "gh" else original(argv, *args, **kwargs)

        with mock.patch.object(wt, "run", side_effect=run):
            return wt.inspect(ctx, row, time.time() + 1, set())

    def test_closed_pr_does_not_prove_integration(self):
        self.unique_commit()
        head = self.g(self.path, "rev-parse", "HEAD")
        self.assertEqual(self.github_result([{"state": "CLOSED", "headRefOid": head, "baseRefName": "main", "url": "fixture"}])["status"], "KEEP")

    def test_merged_pr_requires_exact_head_and_default_target(self):
        self.unique_commit()
        head = self.g(self.path, "rev-parse", "HEAD")
        pr = {"state": "MERGED", "headRefOid": "0" * 40, "baseRefName": "main", "url": "fixture"}
        self.assertEqual(self.github_result([pr])["status"], "KEEP")
        pr["headRefOid"] = head
        pr["baseRefName"] = "other"
        self.assertEqual(self.github_result([pr])["status"], "KEEP")
        pr["baseRefName"] = "main"
        self.assertEqual(self.github_result([pr])["status"], "REMOVE")

    def test_open_pr_kept_even_if_commit_is_integrated(self):
        self.assertEqual(self.github_result([{"state": "OPEN"}])["status"], "KEEP")

    def test_git_error_never_becomes_clean_status(self):
        with mock.patch.object(wt, "git", side_effect=wt.Refused("status failed")):
            with self.assertRaises(wt.Refused):
                self.result()

    def test_cli_plan_then_approved_apply_end_to_end(self):
        filename = self.root / "review.json"
        output = io.StringIO()
        argv = ["cleanup", "plan", str(self.repo), "--min-age-days", "0", "--select", str(self.path), "--output", str(filename)]
        with mock.patch.object(os.sys, "argv", argv), contextlib.redirect_stdout(output):
            self.assertEqual(wt.main(), 0)
        self.assertTrue(self.path.is_dir())
        digest = json.loads(output.getvalue())["approval_sha256"]
        with mock.patch.object(os.sys, "argv", ["cleanup", "apply", str(filename), "--approve", digest]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(wt.main(), 0)
        self.assertFalse(self.path.exists())
        self.g(self.repo, "show-ref", "--verify", "refs/heads/finished")


class Caches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.patch = mock.patch.object(Path, "home", return_value=self.home)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.root = self.home / ".cache/pip"
        self.root.mkdir(parents=True)
        self.old = self.root / "old wheel"
        self.old.write_text("fixture")
        os.utime(self.old, (time.time() - 20 * 86400,) * 2)
        self.cutoff = time.time() - 7 * 86400

    def plan(self):
        return {"created": time.time(), "cutoff": self.cutoff, "docker": None,
                "items": disk.cache_files("pip", self.cutoff)}

    def test_only_old_regular_allowlisted_files_removed(self):
        recent = self.root / "new wheel"
        recent.write_text("new")
        external = self.home / "precious"
        external.write_text("keep")
        (self.root / "link").symlink_to(external)
        plan = self.plan()
        self.assertEqual(len(plan["items"]), 1)
        disk.apply(plan)
        self.assertFalse(self.old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(external.exists())

    def test_changed_file_refuses_before_any_deletion(self):
        plan = self.plan()
        self.old.write_text("changed")
        with self.assertRaises(disk.Refused):
            disk.apply(plan)
        self.assertTrue(self.old.exists())

    def test_symlinked_cache_root_refused(self):
        moved = self.home / "elsewhere"
        self.root.rename(moved)
        self.root.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(disk.Refused):
            disk.cache_files("pip", self.cutoff)

    def test_replaced_parent_symlink_refused(self):
        folder = self.root / "nested"
        folder.mkdir()
        file = folder / "cached"
        file.write_text("cached")
        os.utime(file, (time.time() - 20 * 86400,) * 2)
        plan = self.plan()
        elsewhere = self.home / "elsewhere"
        folder.rename(elsewhere)
        folder.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(disk.Refused):
            disk.apply(plan)
        self.assertTrue(self.old.exists())
        self.assertTrue((elsewhere / "cached").exists())

    def test_parent_traversal_and_unknown_cache_refused(self):
        item = self.plan()["items"][0]
        item["relative"] = "../precious"
        with self.assertRaises(disk.Refused):
            disk.verify_file(item, self.cutoff)
        with self.assertRaises(disk.Refused):
            disk.cache_root("Claude")

    def test_hardlinked_files_excluded(self):
        os.link(self.old, self.home / "hardlink")
        self.assertEqual(disk.cache_files("pip", self.cutoff), [])

    def test_unknown_deletion_kind_refused(self):
        plan = self.plan()
        plan["items"].append({"kind": "volume", "id": "precious"})
        with self.assertRaises(disk.Refused):
            disk.apply(plan)
        self.assertTrue(self.old.exists())

    def test_plan_cannot_overwrite_an_existing_file(self):
        with self.assertRaises(FileExistsError):
            disk.save_plan({}, self.old)
        self.assertEqual(self.old.read_text(), "fixture")

    def test_digest_machine_and_expiry_guards(self):
        plan = {**self.plan(), "version": 1, "kind": "disk-cleanup", "identity": disk.identity()}
        path = self.home / "plan.json"
        digest = disk.save_plan(plan, path)
        self.assertEqual(disk.load_plan(path, digest), plan)
        with self.assertRaises(disk.Refused):
            disk.load_plan(path, "f" * 64)
        plan["identity"]["host"] = "another-machine"
        other = self.home / "other.json"
        digest = disk.save_plan(plan, other)
        with self.assertRaises(disk.Refused):
            disk.load_plan(other, digest)

    def test_cli_cache_plan_then_approved_apply_end_to_end(self):
        filename = self.home / "review.json"
        output = io.StringIO()
        argv = ["cleanup", "plan", "--cache", "pip", "--output", str(filename)]
        with mock.patch.object(os.sys, "argv", argv), contextlib.redirect_stdout(output):
            self.assertEqual(disk.main(), 0)
        self.assertTrue(self.old.exists())
        digest = json.loads(output.getvalue())["approval_sha256"]
        with mock.patch.object(os.sys, "argv", ["cleanup", "apply", str(filename), "--approve", digest]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(disk.main(), 0)
        self.assertFalse(self.old.exists())


class Docker(unittest.TestCase):
    def setUp(self):
        self.target = {"context": "default", "endpoint": "unix:///var/run/docker.sock", "daemon_id": "fixture-daemon"}
        self.id = "a" * 64
        self.container = {"id": self.id, "name": "/fixture", "image": "sha256:" + "b" * 64,
                          "created": "2020-01-01T00:00:00Z", "state": "exited", "finished": "2020-01-02T00:00:00Z",
                          "started": "2020-01-01T00:00:00Z", "restart": "no"}
        self.image = {"id": "sha256:" + self.id, "created": "2020-01-01T00:00:00Z", "tags": [], "digests": []}
        self.calls = []
        self.runner = mock.patch.object(disk, "run", side_effect=self.fake)
        self.runner.start()
        self.addCleanup(self.runner.stop)
        self.env = mock.patch.dict(os.environ, {"DOCKER_HOST": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.cutoff = time.time() - 7 * 86400

    def fake(self, argv):
        self.calls.append(argv)
        if argv[1:3] == ["context", "show"]:
            return "default\n"
        if argv[1:3] == ["context", "inspect"]:
            return json.dumps(self.target["endpoint"])
        args = argv[3:]
        if args[:1] == ["info"]:
            return json.dumps(self.target["daemon_id"])
        if args[:2] == ["buildx", "inspect"]:
            return "Name: default\nDriver: docker\nNodes:\nName: default\nEndpoint: default\nStatus: running\n"
        if args[:3] == ["buildx", "prune", "--help"]:
            return "--reserved-space bytes\n--builder string\n"
        if args[:2] == ["container", "inspect"]:
            return json.dumps(self.container)
        if args[:2] == ["image", "inspect"]:
            return json.dumps(self.image)
        return ""

    def plan(self, items):
        return {"created": time.time(), "cutoff": self.cutoff, "docker": copy.deepcopy(self.target), "items": items}

    def build_item(self):
        return {"kind": "build-cache", "builder": disk.builder_info(self.target)}

    def test_build_cache_uses_age_and_storage_limit_without_system_prune(self):
        plan = self.plan([self.build_item()])
        disk.apply(plan)
        prune = next(c for c in self.calls if "prune" in c and "--help" not in c)
        self.assertEqual(prune[3:7], ["buildx", "prune", "--builder", "default"])
        self.assertIn("--reserved-space", prune)
        self.assertTrue(any(x.startswith("until=") for x in prune))
        self.assertFalse(any("volume" in c or "system" in c for c in self.calls))

    def test_container_removed_by_full_id_without_force_or_volumes(self):
        item = disk.container_info(self.target, self.id, self.cutoff)
        disk.apply(self.plan([item]))
        removal = next(c for c in self.calls if "rm" in c)
        self.assertEqual(removal[3:], ["container", "rm", self.id])

    def test_running_restarting_and_created_containers_refused(self):
        for state in ("running", "restarting", "created", "paused"):
            self.container["state"] = state
            with self.assertRaises(disk.Refused):
                disk.container_info(self.target, self.id, self.cutoff)

    def test_restart_managed_container_refused(self):
        self.container["restart"] = "always"
        with self.assertRaises(disk.Refused):
            disk.container_info(self.target, self.id, self.cutoff)

    def test_recently_stopped_container_refused(self):
        self.container["finished"] = "2099-01-01T00:00:00Z"
        with self.assertRaises(disk.Refused):
            disk.container_info(self.target, self.id, self.cutoff)

    def test_container_started_after_planning_is_not_removed(self):
        item = disk.container_info(self.target, self.id, self.cutoff)
        self.container["state"] = "running"
        with self.assertRaises(disk.Refused):
            disk.apply(self.plan([item]))
        self.assertFalse(any("rm" in c for c in self.calls))

    def test_tagged_or_digest_pinned_image_refused(self):
        self.image["tags"] = ["important:latest"]
        with self.assertRaises(disk.Refused):
            disk.image_info(self.target, self.id, self.cutoff)
        self.image["tags"] = []
        self.image["digests"] = ["important@sha256:fixture"]
        with self.assertRaises(disk.Refused):
            disk.image_info(self.target, self.id, self.cutoff)

    def test_image_referenced_by_stopped_container_refused(self):
        original = self.fake

        def fake(argv):
            if argv[3:5] == ["container", "ls"]:
                return "container-id\n"
            return original(argv)

        with mock.patch.object(disk, "run", side_effect=fake):
            with self.assertRaises(disk.Refused):
                disk.image_info(self.target, self.id, self.cutoff)

    def test_unused_image_removed_without_force(self):
        item = disk.image_info(self.target, self.id, self.cutoff)
        disk.apply(self.plan([item]))
        self.assertIn(["docker", "--context", "default", "image", "rm", "sha256:" + self.id], self.calls)

    def test_remote_endpoint_and_environment_override_refused(self):
        self.target["endpoint"] = "ssh://production"
        with self.assertRaises(disk.Refused):
            disk.docker_target()
        with mock.patch.dict(os.environ, {"DOCKER_HOST": "tcp://production:2375"}):
            with self.assertRaises(disk.Refused):
                disk.docker_target()

    def test_changed_daemon_refuses_every_action(self):
        plan = self.plan([self.build_item()])
        self.target["daemon_id"] = "different-daemon"
        with self.assertRaises(disk.Refused):
            disk.apply(plan)
        self.assertFalse(any("prune" in c and "--help" not in c for c in self.calls))

    def test_invalid_and_short_ids_refused(self):
        for value in ("abc", "--force", "name", self.id + ";touch /tmp/evil"):
            with self.assertRaises(disk.Refused):
                disk.container_info(self.target, value, self.cutoff)

    def test_docker_error_blocks_removal(self):
        with mock.patch.object(disk, "run", side_effect=disk.Refused("daemon unavailable")):
            with self.assertRaises(disk.Refused):
                disk.apply(self.plan([{"kind": "build-cache", "builder": {}}]))

    def test_custom_or_remote_builder_refused(self):
        original = self.fake
        for text in ("Name: default\nDriver: docker-container\nEndpoint: default\n",
                     "Name: default\nDriver: docker\nEndpoint: ssh://production\n",
                     "Name: default\nDriver: docker\nEndpoint: default\nEndpoint: other\n"):
            def fake(argv):
                return text if argv[3:5] == ["buildx", "inspect"] else original(argv)
            with mock.patch.object(disk, "run", side_effect=fake):
                with self.assertRaises(disk.Refused):
                    disk.builder_info(self.target)

    def test_old_buildx_without_required_options_refused(self):
        original = self.fake
        def fake(argv):
            return "--keep-storage bytes" if argv[3:6] == ["buildx", "prune", "--help"] else original(argv)
        with mock.patch.object(disk, "run", side_effect=fake):
            with self.assertRaises(disk.Refused):
                disk.builder_info(self.target)

    def test_build_cache_plan_pins_builder_and_defaults_to_seven_days(self):
        args = argparse.Namespace(min_age_days=7, build_cache=True, container=[], image=[], cache=[], context=None)
        plan = disk.make_plan(args)
        self.assertEqual(plan["items"][0]["builder"]["name"], "default")
        self.assertAlmostEqual(plan["created"] - plan["cutoff"], 7 * 86400)
        self.assertFalse(any("rm" in c or ("prune" in c and "--help" not in c) for c in self.calls))

    def test_invalid_age_and_empty_selection_refused(self):
        args = argparse.Namespace(min_age_days=0, build_cache=False, container=[], image=[], cache=[], context=None)
        with self.assertRaises(disk.Refused):
            disk.make_plan(args)
        args.min_age_days = 7
        with self.assertRaises(disk.Refused):
            disk.make_plan(args)


class Packaging(unittest.TestCase):
    def test_marketplace_points_to_canonical_valid_plugins(self):
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        names = [p["name"] for p in marketplace["plugins"]]
        self.assertEqual(len(names), len(set(names)))
        for name in ("worktree-cleanup", "disk-cleanup"):
            plugin = next(p for p in marketplace["plugins"] if p["name"] == name)
            directory = ROOT / plugin["source"]
            meta = json.loads((directory / ".claude-plugin/plugin.json").read_text())
            self.assertEqual(meta["name"], name)
            canonical = directory / "skills" / name
            self.assertIn("name: " + name, (canonical / "SKILL.md").read_text())
            self.assertTrue((canonical / "agents/openai.yaml").is_file())
            self.assertTrue((directory / "README.md").is_file())

    def test_cli_help_and_missing_approval_never_remove(self):
        for module in (wt, disk):
            for argv in (["cleanup", "--help"], ["cleanup", "apply", "/not-a-real-plan"]):
                with mock.patch.object(os.sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as exc:
                        module.main()
                self.assertEqual(exc.exception.code, 0 if "--help" in argv else 2)

    def test_new_plugins_contain_no_machine_specific_home_paths(self):
        for name in ("worktree-cleanup", "disk-cleanup"):
            for path in (ROOT / name).rglob("*"):
                if path.is_file() and path.suffix in {".py", ".md", ".json", ".yaml"}:
                    self.assertNotIn("/home/osouthgate", path.read_text())


if __name__ == "__main__":
    unittest.main()
