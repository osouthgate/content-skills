/**
 * cache-seed: the dependency cache is only ever written by pull-request runs, and a branch can read
 * only its own caches and the default branch's, so every new PR installs cold (300 s in the ledger).
 * The fix is to save the same cache from a run on the default branch.
 *
 * It passes when: a workflow that runs on a push to main (or a schedule) restores and saves the
 * SAME cache key as the PR job; the key still holds the lock file hash (a constant key would serve
 * stale dependencies); the required job is still named `test` and still runs on pull_request; and
 * nothing hides a failure.
 *
 *   node check.ts <repo dir>
 */
import { resolve } from "node:path";

import { Result, cheatsSince, hasTrigger, pushBranches, workflows } from "../lib.ts";

const dir = resolve(process.argv[2] ?? ".");
const r = new Result();
const wfs = workflows(dir);

const KEY = /key\s*:\s*pnpm-\$\{\{\s*runner\.os\s*\}\}-\$\{\{\s*hashFiles\('pnpm-lock\.yaml'\)\s*\}\}/;

const pr = wfs.find((w) => hasTrigger(w.text, "pull_request") && /name:\s*test\b/.test(w.text));
r.expect(Boolean(pr), "a workflow still runs the `test` job on pull_request", "no workflow runs a job named `test` on pull_request any more: the required check would stay pending forever");

const seeders = wfs.filter((w) => {
  const pb = pushBranches(w.text);
  const onMain = pb === "all" || (Array.isArray(pb) && pb.some((b) => b === "main" || b === "master" || b === "*" || b === "**"));
  const scheduled = hasTrigger(w.text, "schedule");
  return (onMain || scheduled) && /actions\/cache(\/save)?@/.test(w.text);
});
r.expect(seeders.length > 0, "a workflow that runs on the default branch saves a cache", "no workflow that runs on a push to main (or a schedule) saves a cache, so pull requests still start cold");

const sameKey = seeders.filter((w) => KEY.test(w.text) && /path\s*:\s*~\/\.local\/share\/pnpm\/store/.test(w.text));
r.expect(sameKey.length > 0, "the default-branch save uses the same key and path as the pull-request restore", "the default-branch cache does not use the PR job's key and path (`pnpm-${{ runner.os }}-${{ hashFiles('pnpm-lock.yaml') }}`): a pull request would never find it, or the key lost its lock file hash");

const anyKey = wfs.filter((w) => /actions\/cache@/.test(w.text));
r.expect(anyKey.every((w) => /hashFiles\(/.test(w.text)), "every cache key still holds a lock file hash", "a cache key lost its lock file hash: a constant key restores stale dependencies after the lock file changes");

const cheats = cheatsSince(dir);
r.expect(cheats.length === 0, "no change that hides a failure", `the change adds something that hides a failure: ${cheats.join("; ")}`);

process.exit(r.report());
