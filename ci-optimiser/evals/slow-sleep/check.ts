/**
 * slow-sleep: one test waits a fixed 3 s for a service that is ready after 50 ms and offers
 * `whenReady()`. The fix is to wait on the event instead of the clock.
 *
 * It RUNS the repository's tests (Node's own runner, offline) and passes when: the run is fast;
 * every test that ran before still runs, by name, and passes; no assertion line was removed or
 * changed; and nothing hides a failure (a skip, a retry, a wider timeout).
 *
 *   node check.ts <repo dir>
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { compareTests, parseDiff, parseJUnit, renderTests, scanDiff } from "../../skills/ci-optimiser/scripts/guard-lib.ts";
import { Result, baseRef, cheatsSince, git } from "../lib.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const dir = resolve(process.argv[2] ?? ".");
const r = new Result();
const MAX_MS = 2000;

const expected = JSON.parse(readFileSync(join(HERE, "expected-tests.json"), "utf-8")) as string[];
const before = new Map(expected.map((k) => [k, "pass" as const]));

const out = mkdtempSync(join(tmpdir(), "slow-sleep-"));
try {
  // Inside another `node --test` run (as in this skill's own tests) the variable below makes a nested
  // `node --test` act as a child and find no files, so the sample's run must not inherit it.
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const started = Date.now();
  const ran = spawnSync(process.execPath, ["--test", "--test-reporter=junit", `--test-reporter-destination=${join(out, "junit.xml")}`], { cwd: dir, encoding: "utf-8", env });
  const elapsed = Date.now() - started;
  r.expect(elapsed < MAX_MS, `the test run took ${elapsed} ms`, `the test run took ${elapsed} ms: the fixed wait is still there (it must finish in under ${MAX_MS} ms)`);
  let after = new Map();
  try {
    after = parseJUnit(readFileSync(join(out, "junit.xml"), "utf-8"));
  } catch {
    r.failures.push(`no JUnit report: the tests did not run (exit ${ran.status})`);
  }
  const t = compareTests(before, after);
  r.expect(t.ok, "every test that ran before still runs and passes", `tests lost, skipped or newly failing:\n${renderTests(t)}`);
  r.expect(ran.status === 0, "the suite passes", `the suite exits ${ran.status}`);
} finally {
  rmSync(out, { recursive: true, force: true });
}

const removed = scanDiff(parseDiff(git(dir, "diff", baseRef(dir), "--unified=0", "--no-color"))).filter((f) => f.kind === "review");
r.expect(removed.length === 0, "no assertion removed or changed", `an assertion line was removed or changed: ${removed.map((f) => `${f.file}: ${f.line}`).join("; ")}`);

const cheats = cheatsSince(dir);
r.expect(cheats.length === 0, "no change that hides a failure", `the change adds something that hides a failure: ${cheats.join("; ")}`);

process.exit(r.report());
