// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { type LedgerRun, byDay, cohorts, formatDay, renderReport } from "../scripts/ledger-lib.ts";

const SCRIPTS = join(dirname(fileURLToPath(import.meta.url)), "..", "scripts");

function run(id: number, createdAt: string, seconds: number, o: { jobs?: { name: string; seconds: number }[]; conclusion?: string; wall?: number } = {}): LedgerRun {
  const jobs = (o.jobs ?? [{ name: "test", seconds }]).map((j) => ({ name: j.name, conclusion: o.conclusion ?? "success", runner: "r", labels: ["ubuntu-latest"], seconds: j.seconds, queueSeconds: 2, steps: [] }));
  return {
    v: 1, key: `${id}:1`, runId: id, attempt: 1, workflow: "CI", path: ".github/workflows/ci.yml", event: "pull_request", branch: "feature",
    sha: `sha${id}`, prs: [1], title: `c${id}`, conclusion: o.conclusion ?? "success", createdAt, startedAt: createdAt, completedAt: createdAt,
    wallSeconds: o.wall ?? seconds + 20, queueSeconds: 2, jobSeconds: jobs.reduce((a, j) => a + j.seconds, 0), jobs, url: null,
  };
}

/** Five slow runs on Nov 3-7, five fast runs on Nov 12-16: a clear speed-up merged on the 10th. */
function fixtureRuns(): LedgerRun[] {
  const out: LedgerRun[] = [];
  for (let i = 0; i < 5; i++) out.push(run(100 + i, `2026-11-0${3 + i}T10:00:00Z`, 600 + i * 10));
  for (let i = 0; i < 5; i++) out.push(run(200 + i, `2026-11-1${2 + i}T10:00:00Z`, 300 + i * 10));
  return out;
}

function setup(runs: LedgerRun[], pullState?: Record<string, unknown>): string {
  const root = mkdtempSync(join(tmpdir(), "ci-compare-"));
  const dir = join(root, "docs/ledger/ci");
  mkdirSync(dir, { recursive: true });
  for (const [day, rs] of byDay(runs)) writeFileSync(join(dir, `${day}.jsonl`), formatDay(rs));
  if (pullState) {
    mkdirSync(join(root, "test-results/ci-ledger"), { recursive: true });
    writeFileSync(join(root, "test-results/ci-ledger/pull-state.json"), JSON.stringify(pullState));
  }
  return root;
}

function ledger(root: string, ...a: string[]) {
  return spawnSync(process.execPath, ["--disable-warning=ExperimentalWarning", join(SCRIPTS, "ledger.ts"), ...a, "--root", root], { encoding: "utf-8" });
}

const WINDOWS = ["--job", "test", "--before", "2026-11-01..2026-11-10", "--after", "2026-11-10..2026-11-20"];
const SETTLED = { pulledAt: "2026-11-25T00:00:00Z", since: "2026-11-01", workflow: null };

test("compare: a real speed-up gets a median faster verdict with an interval", () => {
  const root = setup(fixtureRuns(), SETTLED);
  try {
    const r = ledger(root, "compare", ...WINDOWS);
    assert.equal(r.status, 0, r.stdout + r.stderr);
    assert.match(r.stdout, /verdict: median faster \(5 before, 5 after\)/);
    assert.match(r.stdout, /before .*: 5 runs, median 10m 20s/);
    assert.match(r.stdout, /after .*: 5 runs, median 5m 20s/);
    assert.match(r.stdout, /exact 95% interval/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("compare: with no record of the last pull it refuses, and says how to fix that", () => {
  const root = setup(fixtureRuns());
  try {
    const r = ledger(root, "compare", ...WINDOWS);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /refused: no record of when this ledger was pulled/);
    assert.equal(ledger(root, "compare", ...WINDOWS, "--assume-settled").status, 0);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("compare: a pull made before the after window settled is refused, however it is asked", () => {
  const root = setup(fixtureRuns(), { ...SETTLED, pulledAt: "2026-11-20T01:00:00Z" });
  try {
    const r = ledger(root, "compare", ...WINDOWS);
    assert.equal(r.status, 2);
    assert.match(r.stderr, /before the after window had settled/);
    const future = ledger(root, "compare", "--job", "test", "--before", "2026-11-01..2026-11-10", "--after", `2026-11-10..${new Date(Date.now() + 3_600_000).toISOString().slice(0, 19)}Z`, "--assume-settled");
    assert.equal(future.status, 2, "--assume-settled cannot skip the clock");
    assert.match(future.stderr, /less than 2 h ago/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("compare: too few runs exits 3 with no timings claimed", () => {
  const root = setup(fixtureRuns().slice(2), SETTLED);
  try {
    const r = ledger(root, "compare", ...WINDOWS);
    assert.equal(r.status, 3, r.stdout + r.stderr);
    assert.match(r.stdout, /verdict: not enough runs yet/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("compare: failures after beyond chance make the speed-up invalid (exit 4)", () => {
  const runs = fixtureRuns();
  for (let i = 0; i < 7; i++) runs.push(run(300 + i, `2026-11-1${2 + (i % 4)}T12:00:00Z`, 12, { conclusion: "failure" }));
  const root = setup(runs, SETTLED);
  try {
    const r = ledger(root, "compare", ...WINDOWS);
    assert.equal(r.status, 4, r.stdout);
    assert.match(r.stdout, /verdict: not valid: more runs failed after/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("compare: bad input fails loudly", () => {
  const root = setup(fixtureRuns(), SETTLED);
  try {
    assert.match(ledger(root, "compare", "--job", "test", "--after", "2026-11-10..2026-11-20").stderr, /--before is required/);
    assert.match(ledger(root, "compare", "--job", "test", "--before", "2026-11-12..2026-11-10", "--after", "2026-11-10..2026-11-20").stderr, /ends before it starts/);
    assert.match(ledger(root, "compare", "--job", "test", "--before", "2026-11-01..2026-11-12", "--after", "2026-11-10..2026-11-20").stderr, /overlap/);
    assert.match(ledger(root, "compare", "--job", "test", "--before", "soon..2026-11-10", "--after", "2026-11-10..2026-11-20").stderr, /not a UTC date/);
    assert.match(ledger(root, "compare", ...WINDOWS, "--min-runs", "3").stderr, /fewest a 95% interval can use/);
    const none = ledger(root, "compare", "--job", "nope", ...WINDOWS.slice(2));
    assert.equal(none.status, 2);
    assert.match(none.stderr, /no job "nope"/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("cohorts group passed runs by their longest job, so a docs-only run is not blended in", () => {
  const full = (id: number, h: number) => run(id, `2026-11-10T${String(h).padStart(2, "0")}:00:00Z`, 0, { jobs: [{ name: "lint", seconds: 60 }, { name: "test", seconds: 600 }], wall: 640 });
  const docs = (id: number, h: number) => run(id, `2026-11-10T${String(h).padStart(2, "0")}:00:00Z`, 0, { jobs: [{ name: "lint", seconds: 60 }], wall: 75 });
  const runs = [full(1, 1), full(2, 2), full(3, 3), docs(4, 4), docs(5, 5)];
  const got = cohorts(runs, { from: "2026-11-10T00:00:00Z", to: "2026-11-11T00:00:00Z" });
  assert.deepEqual(got.map((g) => [g.longestJob, g.runs, g.wallP50]), [["test", 3, 640], ["lint", 2, 75]]);
  assert.ok(got[0]!.share > 0.9, "the full runs hold nearly all of the wait");
  const md = renderReport(runs, { days: 2, now: new Date("2026-11-11T12:00:00Z"), branch: "main" });
  assert.match(md, /## Wall time by kind of run/);
  assert.match(md, /fast runs finish first/);
});
