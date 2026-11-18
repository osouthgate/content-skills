// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { changePoints, dayOf, formatDay, jobStats, mergeDay, normaliseRun, parseDay, parseJobs, parseRuns, quantile, renderReport, stepStats } from "../scripts/ledger-lib.ts";
import { scanWorkflow } from "../scripts/workflow-scan.ts";

const SCRIPTS = join(dirname(fileURLToPath(import.meta.url)), "..", "scripts");

function iso(base: string, plusSeconds: number): string {
  return new Date(Date.parse(base) + plusSeconds * 1000).toISOString().replace(".000Z", "Z");
}

function rawRun(id: number, created: string, extra: Record<string, unknown> = {}) {
  return { id, name: "CI", path: ".github/workflows/ci.yml", run_attempt: 1, event: "push", conclusion: "success", head_branch: "main", head_sha: `sha${id}`, display_title: `Commit ${id}\nbody`, pull_requests: [{ number: 7 }], created_at: created, run_started_at: iso(created, 5), updated_at: iso(created, 200), html_url: `https://example.test/runs/${id}`, ...extra };
}

function rawJob(name: string, created: string, secs: number, conclusion = "success") {
  return { id: 1, name, conclusion, created_at: iso(created, 5), started_at: iso(created, 10), completed_at: iso(created, 10 + secs), runner_name: "r1", labels: ["ubuntu-latest"], steps: [{ name: "slow step", conclusion, started_at: iso(created, 10), completed_at: iso(created, 10 + secs) }, { name: "fast", conclusion, started_at: iso(created, 10), completed_at: iso(created, 12) }] };
}

function ledgerRun(id: number, created: string, secs: number, conclusion = "success") {
  const [run] = parseRuns({ workflow_runs: [rawRun(id, created, { conclusion })] });
  return normaliseRun(run!, parseJobs({ jobs: [rawJob("test", created, secs, conclusion)] }));
}

test("normaliseRun keeps the commit, PRs, times and only slow steps", () => {
  const r = ledgerRun(1, "2026-11-10T10:00:00Z", 120);
  assert.equal(r.key, "1:1");
  assert.equal(r.title, "Commit 1");
  assert.deepEqual(r.prs, [7]);
  assert.equal(r.jobs[0]!.seconds, 120);
  assert.equal(r.jobs[0]!.queueSeconds, 5);
  assert.equal(r.queueSeconds, 10);
  assert.deepEqual(r.jobs[0]!.steps.map((s) => s.name), ["slow step"]);
  assert.equal(dayOf(r), "2026-11-10");
});

test("parseRuns refuses a bad shape and drops a run with a free-text date", () => {
  assert.throws(() => parseRuns({}), /no workflow_runs/);
  assert.equal(parseRuns({ workflow_runs: [{ ...rawRun(2, "2026-11-10T10:00:00Z"), created_at: "../../etc" }] }).length, 0);
});

test("day files round-trip and merge by key", () => {
  const a = ledgerRun(1, "2026-11-10T10:00:00Z", 60);
  const b = ledgerRun(2, "2026-11-10T09:00:00Z", 60);
  const a2 = { ...a, title: "replaced" };
  const merged = mergeDay([a], [b, a2]);
  assert.deepEqual(merged.map((r) => r.key), ["2:1", "1:1"]);
  assert.equal(merged[1]!.title, "replaced");
  assert.deepEqual(parseDay(formatDay(merged), "x"), merged);
  assert.throws(() => parseDay("{not json\n", "d.jsonl"), /d\.jsonl:1: not valid JSON/);
  assert.throws(() => parseDay('{"v":2}\n', "d.jsonl"), /d\.jsonl:1: not a ledger run/);
});

test("quantile is nearest-rank", () => {
  assert.equal(quantile([], 0.5), null);
  assert.equal(quantile([5, 1, 3], 0.5), 3);
  assert.equal(quantile([1, 2, 3, 4], 0.9), 4);
});

test("a fast failure counts in total minutes but not in the median", () => {
  const runs = [ledgerRun(1, "2026-11-10T10:00:00Z", 600), ledgerRun(2, "2026-11-10T11:00:00Z", 600), ledgerRun(3, "2026-11-10T12:00:00Z", 5, "failure"), ledgerRun(4, "2026-11-10T13:00:00Z", 5, "failure"), ledgerRun(5, "2026-11-10T14:00:00Z", 5, "failure")];
  const win = { from: "2026-11-10T00:00:00Z", to: "2026-11-11T00:00:00Z" };
  const [j] = jobStats(runs, win, { from: "2026-11-09T00:00:00Z", to: win.from });
  assert.equal(j!.p50, 600);
  assert.equal(j!.totalSeconds, 1215);
  assert.equal(j!.failures, 3);
  const [s] = stepStats(runs, win);
  assert.equal(s!.p50, 600);
});

test("changePoints names the first commit after a slowdown", () => {
  const runs = Array.from({ length: 10 }, (_, i) => ledgerRun(i + 1, iso("2026-11-01T00:00:00Z", i * 3600), i < 5 ? 100 : 300));
  const [cp] = changePoints(runs, { branch: "main" });
  assert.equal(cp!.sha, "sha6");
  assert.equal(cp!.before, 100);
  assert.equal(cp!.after, 300);
});

test("renderReport has every section", () => {
  const md = renderReport([ledgerRun(1, "2026-11-10T10:00:00Z", 60)], { days: 7, now: new Date("2026-11-12T00:00:00Z"), branch: "main" });
  for (const h of ["## Workflows", "## Jobs by total runner time", "## Slowest steps", "## Where a job changed speed"]) assert.match(md, new RegExp(h));
});

test("workflow scan finds the checklist items and stays quiet on a tidy file", () => {
  const slow = `name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: npm ci
      - run: npx playwright install chromium
${Array.from({ length: 9 }, (_, i) => `      - run: node t${i}.js`).join("\n")}
`;
  const codes = scanWorkflow("ci.yml", slow).map((h) => h.code).sort();
  assert.deepEqual(codes, ["browser-download", "full-history", "long-serial-job", "no-concurrency", "no-dependency-cache", "no-timeout"]);
  const tidy = `on: [pull_request]
concurrency:
  group: ci-\${{ github.ref }}
  cancel-in-progress: true
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          cache: npm
      - run: npm ci
`;
  assert.deepEqual(scanWorkflow("ci.yml", tidy), []);
  const noInstall = "on: push\njobs:\n  py:\n    timeout-minutes: 5\n    steps:\n      - uses: actions/setup-python@v5\n      - run: python3 -m unittest\n";
  assert.deepEqual(scanWorkflow("py.yml", noInstall), [], "no cache hint when nothing is installed");
  assert.equal(scanWorkflow("t.yml", "on:\n  pull_request_target:\njobs:\n  a:\n    timeout-minutes: 1\n    steps:\n      - run: x\n").length, 0);
});

test("ledger CLI: import, report and flag checks, offline", () => {
  const root = mkdtempSync(join(tmpdir(), "ci-ledger-"));
  const saved = join(root, "saved");
  mkdirSync(saved);
  const created = new Date(Date.now() - 86_400_000).toISOString().replace(/\.\d+Z$/, "Z");
  writeFileSync(join(saved, "runs.json"), JSON.stringify({ workflow_runs: [rawRun(11, created), rawRun(12, created)] }));
  writeFileSync(join(saved, "jobs-11.json"), JSON.stringify({ jobs: [rawJob("test", created, 90)] }));
  const node = (...a: string[]) => spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(SCRIPTS, "ledger.ts"), ...a], { cwd: root, encoding: "utf-8" });
  const imp = node("import", "--root", root, "saved");
  assert.equal(imp.status, 0, imp.stderr);
  assert.match(imp.stdout, /1 runs \(1 skipped: no jobs file\)/);
  assert.equal(readdirSync(join(root, "docs/ledger/ci")).length, 1);
  const again = node("import", "saved");
  assert.match(again.stdout, /0 lines added/);
  const rep = node("report", "--days", "3", "--out", "out/r.md");
  assert.equal(rep.status, 0, rep.stderr);
  assert.match(readFileSync(join(root, "out/r.md"), "utf-8"), /\| CI \| test \| 1 \|/);
  assert.match(node("report", "--days", "abc").stderr, /--days: expected a whole number/);
  assert.match(node("report", "--days").stderr, /--days needs a value/);
  assert.equal(node("nope").status, 2);
  const brief = spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(SCRIPTS, "optimise.ts"), "--root", root, "--days", "3"], { cwd: root, encoding: "utf-8" });
  assert.equal(brief.status, 0, brief.stderr);
  const text = readFileSync(join(root, "test-results/ci-optimiser/brief.md"), "utf-8");
  assert.match(text, /## CI report/);
  assert.match(text, /No .github\/workflows folder/);
  execFileSync("git", ["--version"]);
});
