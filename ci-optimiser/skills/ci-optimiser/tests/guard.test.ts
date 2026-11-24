// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compareTests, parseDiff, parseJUnit, renderFindings, renderTests, scanDiff, swallowedFailures } from "../scripts/guard-lib.ts";

const SCRIPTS = join(dirname(fileURLToPath(import.meta.url)), "..", "scripts");

const change = (file: string, added: string[], removed: string[] = []) => ({ file, added, removed });
const whats = (added: string[], file = ".github/workflows/ci.yml", removed: string[] = []): string[] => scanDiff([change(file, added, removed)]).map((f) => f.what);

test("parseDiff reads added and removed lines per file", () => {
  const diff = ["diff --git a/x.yml b/x.yml", "--- a/x.yml", "+++ b/x.yml", "@@ -1 +1 @@", "-timeout-minutes: 10", "+timeout-minutes: 30", "--- /dev/null", "+++ b/new.ts", "+const a = 1;"].join("\n");
  const got = parseDiff(diff);
  assert.deepEqual(got.map((c) => c.file), ["x.yml", "new.ts"]);
  assert.deepEqual(got[0]!.removed, ["timeout-minutes: 10"]);
  assert.deepEqual(got[0]!.added, ["timeout-minutes: 30"]);
});

test("scanDiff finds each way to go faster by hiding a failure", () => {
  assert.match(whats(["    continue-on-error: true"])[0]!, /continue-on-error/);
  assert.match(whats(["      - uses: nick-fields/retry@v3"])[0]!, /retry/);
  assert.match(whats(["  retries: 2,"], "playwright.config.ts")[0]!, /retry/);
  assert.match(whats(["it.skip('slow one', () => {})"], "src/a.test.ts")[0]!, /skipped/);
  assert.match(whats(["describe.only('x', () => {})"], "src/a.test.ts")[0]!, /skipped/);
  assert.match(whats(["      - run: git push --no-verify"])[0]!, /bypass/);
  assert.match(whats(["on: pull_request_target"])[0]!, /pull_request_target/);
  assert.match(whats(["permissions: write-all"])[0]!, /wider permissions/);
  assert.match(whats(["    contents: write"])[0]!, /wider permissions/);
  assert.match(whats(["      - run: pnpm test --maxWorkers=1"])[0]!, /fewer workers/);
  assert.match(whats(["    timeout-minutes: 120"])[0]!, /very long timeout/);
});

test("a timeout that grew is a cheat; one that shrank is not", () => {
  assert.ok(whats(["    timeout-minutes: 30"], ".github/workflows/ci.yml", ["    timeout-minutes: 10"]).includes("a wider timeout"));
  assert.deepEqual(whats(["    timeout-minutes: 8"], ".github/workflows/ci.yml", ["    timeout-minutes: 10"]), []);
});

test("`|| true` is a cheat after a check and ordinary shell after grep", () => {
  assert.deepEqual(swallowedFailures(["      - run: pnpm test || true"]), ["- run: pnpm test || true"]);
  assert.deepEqual(swallowedFailures(["git merge-base --is-ancestor a b || true"]), []);
  assert.deepEqual(swallowedFailures(["pnpm lint \\", "  || true"]).length, 1);
  assert.ok(whats(["      - run: npx vitest run || true"]).includes("`|| true` after a check"));
});

test("comments and prose are not code: a note about a retry is fine", () => {
  assert.deepEqual(whats(["# do not add a retry here", "    # continue-on-error: true is banned"]), []);
  assert.deepEqual(whats(["We added a retry to the docs"], "docs/notes.md"), []);
  assert.deepEqual(whats(['{"retries": 3}'], "docs/ledger/ci/2026-11-01.jsonl"), []);
});

test("a removed assertion is for a person to review, not a hard failure", () => {
  const found = scanDiff([change("test/billing.test.ts", ["expect(total).toBe(100)"], ["expect(total).toBe(120)"])]);
  assert.equal(found.length, 1);
  assert.equal(found[0]!.kind, "review");
  assert.deepEqual(scanDiff([change("src/billing.ts", [], ["expect(total).toBe(120)"])]), [], "only test files count");
  assert.match(renderFindings(found), /REVIEW/);
});

test("a clean change says so", () => {
  assert.match(renderFindings(scanDiff([change(".github/workflows/ci.yml", ["    cache: pnpm"])])), /nothing added that hides a failure/);
});

const junit = (cases: string): string => `<?xml version="1.0"?><testsuites><testsuite name="s">${cases}</testsuite></testsuites>`;

test("parseJUnit reads pass, fail, error and skipped, self-closing or not", () => {
  const xml = junit(`
    <testcase classname="a.B" name="passes" time="0.1"/>
    <testcase classname="a.B" name="fails"><failure message="no">trace</failure></testcase>
    <testcase classname="a.B" name="errors"><error message="x"/></testcase>
    <testcase classname="a.B" name="skips"><skipped/></testcase>
    <testcase classname="a.B" name="a &amp; b"/>`);
  const m = parseJUnit(xml);
  assert.deepEqual([...m], [
    ["a.B::passes", "pass"],
    ["a.B::fails", "fail"],
    ["a.B::errors", "fail"],
    ["a.B::skips", "skip"],
    ["a.B::a & b", "pass"],
  ]);
});

test("a repeated name keeps both: parametrised tests and shards must not collapse", () => {
  const m = parseJUnit(junit(`<testcase classname="c" name="p"/><testcase classname="c" name="p"/>`));
  assert.deepEqual([...m.keys()], ["c::p", "c::p#2"]);
  const two = parseJUnit(junit(`<testcase classname="c" name="p"/>`), parseJUnit(junit(`<testcase classname="c" name="p"/>`)));
  assert.equal(two.size, 2);
});

test("compareTests names every test that stopped, was skipped, or newly fails", () => {
  const before = parseJUnit(junit(`<testcase classname="t" name="a"/><testcase classname="t" name="b"/><testcase classname="t" name="c"/><testcase classname="t" name="d"/>`));
  const after = parseJUnit(junit(`<testcase classname="t" name="a"/><testcase classname="t" name="b"><skipped/></testcase><testcase classname="t" name="c"><failure/></testcase><testcase classname="t" name="e"/>`));
  const r = compareTests(before, after);
  assert.deepEqual(r.stopped, ["t::d"]);
  assert.deepEqual(r.newlySkipped, ["t::b"]);
  assert.deepEqual(r.newlyFailing, ["t::c"]);
  assert.equal(r.added, 1);
  assert.equal(r.ok, false);
  assert.match(renderTests(r), /verdict: FAIL/);
  const same = compareTests(before, before);
  assert.equal(same.ok, true);
  assert.match(renderTests(same), /verdict: ok/);
});

test("a test that already failed before may keep failing: only new damage counts", () => {
  const before = parseJUnit(junit(`<testcase classname="t" name="a"><failure/></testcase>`));
  assert.equal(compareTests(before, before).ok, true);
});

function cli(args: string[], cwd: string) {
  return spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(SCRIPTS, "diff-guard.ts"), ...args], { cwd, encoding: "utf-8" });
}

test("diff-guard CLI: a speed-up that adds a retry and a skip exits 4; a clean cache change exits 0", () => {
  const repo = mkdtempSync(join(tmpdir(), "ci-guard-"));
  try {
    const git = (...a: string[]) => execFileSync("git", ["-C", repo, "-c", "user.email=t@example.test", "-c", "user.name=t", ...a], { encoding: "utf-8" });
    git("init", "-q");
    mkdirSync(join(repo, ".github/workflows"), { recursive: true });
    writeFileSync(join(repo, ".github/workflows/ci.yml"), "name: CI\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n    steps:\n      - run: pnpm test\n");
    git("add", ".");
    git("commit", "-q", "-m", "sample");
    git("tag", "sample");

    writeFileSync(join(repo, ".github/workflows/ci.yml"), "name: CI\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n    steps:\n      - uses: actions/setup-node@v4\n        with:\n          cache: pnpm\n      - run: pnpm test\n");
    const clean = cli(["diff", "--base", "sample"], repo);
    assert.equal(clean.status, 0, clean.stdout + clean.stderr);

    writeFileSync(join(repo, ".github/workflows/ci.yml"), "name: CI\non: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n    steps:\n      - uses: nick-fields/retry@v3\n      - run: pnpm test || true\n");
    writeFileSync(join(repo, "extra.test.ts"), "it.skip('slow', () => {})\n");
    const dirty = cli(["diff", "--base", "sample"], repo);
    assert.equal(dirty.status, 4, dirty.stdout + dirty.stderr);
    assert.match(dirty.stdout, /CHEAT .*ci\.yml: a retry/);
    assert.match(dirty.stdout, /CHEAT .*extra\.test\.ts: a skipped test/, "an untracked new file is part of the change");
    assert.match(dirty.stdout, /`\|\| true` after a check/);
  } finally {
    rmSync(repo, { recursive: true, force: true });
  }
});

test("diff-guard CLI: tests compares two report folders by name", () => {
  const root = mkdtempSync(join(tmpdir(), "ci-guard-junit-"));
  try {
    for (const side of ["before", "after"]) mkdirSync(join(root, side));
    writeFileSync(join(root, "before/report.xml"), junit(`<testcase classname="billing" name="refund_rounding"/><testcase classname="billing" name="tax"/>`));
    writeFileSync(join(root, "after/report.xml"), junit(`<testcase classname="billing" name="tax"/>`));
    const bad = cli(["tests", "--before", join(root, "before"), "--after", join(root, "after")], root);
    assert.equal(bad.status, 4, bad.stdout + bad.stderr);
    assert.match(bad.stdout, /stopped running:\n {2}billing::refund_rounding/);
    writeFileSync(join(root, "after/report.xml"), junit(`<testcase classname="billing" name="tax"/><testcase classname="billing" name="refund_rounding"/>`));
    assert.equal(cli(["tests", "--before", join(root, "before"), "--after", join(root, "after")], root).status, 0);
    assert.equal(cli(["tests", "--before", join(root, "before")], root).status, 1);
    assert.equal(cli(["nope"], root).status, 2);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
