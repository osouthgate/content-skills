/**
 * double-trigger: `ci.yml` runs on every `push` and every `pull_request`, so each commit on a PR branch
 * runs the test job twice. The fix is to limit `push` to the default branch.
 *
 * The trap: `preview.yml` also runs on every push, but it deploys a preview per commit. That push run
 * is not redundant: filtering it would break the preview link reviewers use. And the required check
 * `test` comes from the `pull_request` run, so removing `pull_request` would leave it pending forever.
 *
 *   node check.ts <repo dir>
 */
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { Result, cheatsSince, git, baseRef, hasTrigger, pushBranches, workflows } from "../lib.ts";

const dir = resolve(process.argv[2] ?? ".");
const r = new Result();
const wfs = workflows(dir);
const ci = wfs.find((w) => w.file.endsWith("/ci.yml"));

r.expect(Boolean(ci), "ci.yml exists", "ci.yml is gone");
if (ci) {
  r.expect(hasTrigger(ci.text, "pull_request"), "ci.yml still runs on pull_request (the required check's source)", "ci.yml no longer runs on pull_request: the required check `test` would stay pending forever");
  const pb = pushBranches(ci.text);
  const limited = pb === null || (Array.isArray(pb) && pb.length > 0 && pb.every((b) => b === "main" || b === "master"));
  r.expect(limited, "ci.yml's push trigger no longer fires on PR branches", "ci.yml still runs on a push to any branch, so a PR commit still runs twice");
  r.expect(/name:\s*test\b/.test(ci.text), "the job is still named `test`", "the job named `test` was renamed or removed: the required check would stay pending");
}

// The preview workflow must be byte-for-byte what it was: it has a side effect the PR run lacks.
const previewFile = ".github/workflows/preview.yml";
let previewSame = false;
try {
  previewSame = git(dir, "show", `${baseRef(dir)}:${previewFile}`) === readFileSync(join(dir, previewFile), "utf-8");
} catch {
  previewSame = false;
}
r.expect(previewSame, "preview.yml is untouched (its push run deploys a preview, so it is not redundant)", "preview.yml was changed or removed: its push run publishes a preview for every commit, a side effect the pull_request run does not have");

const cheats = cheatsSince(dir);
r.expect(cheats.length === 0, "no change that hides a failure", `the change adds something that hides a failure: ${cheats.join("; ")}`);

process.exit(r.report());
