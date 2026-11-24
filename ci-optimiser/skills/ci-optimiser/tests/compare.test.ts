// Run: node --test tests/*.test.ts   (Node 22.18+; no installs)
import { test } from "node:test";
import assert from "node:assert/strict";

import type { LedgerRun } from "../scripts/ledger-lib.ts";
import {
  CompareError,
  compareSamples,
  criticalCount,
  exactInterval,
  failedAfterThreshold,
  fisherOneSided,
  renderComparison,
  selectSamples,
  settledProblem,
} from "../scripts/compare-lib.ts";

function run(id: number, createdAt: string, jobSeconds: number | null, o: { conclusion?: string; label?: string; workflow?: string; event?: string; branch?: string; job?: string; wall?: number } = {}): LedgerRun {
  const conclusion = o.conclusion ?? "success";
  return {
    v: 1,
    key: `${id}:1`,
    runId: id,
    attempt: 1,
    workflow: o.workflow ?? "CI",
    path: ".github/workflows/ci.yml",
    event: o.event ?? "pull_request",
    branch: o.branch ?? "feature",
    sha: `sha${id}`,
    prs: [1],
    title: `commit ${id}`,
    conclusion,
    createdAt,
    startedAt: createdAt,
    completedAt: createdAt,
    wallSeconds: o.wall ?? (jobSeconds ?? 0) + 20,
    queueSeconds: 5,
    jobSeconds: jobSeconds ?? 0,
    jobs: [{ name: o.job ?? "test", conclusion, runner: "r1", labels: [o.label ?? "ubuntu-latest"], seconds: jobSeconds, queueSeconds: 3, steps: [] }],
    url: null,
  };
}

const day = (d: number, h = 10): string => `2026-11-${String(d).padStart(2, "0")}T${String(h).padStart(2, "0")}:00:00Z`;

test("the 5-run floor is arithmetic: 3 a side can never rule out no change, 4 only if all 16 pairs agree, 5 leaves room for 2 pairs", () => {
  assert.equal(criticalCount(3, 3).c, -1);
  assert.equal(criticalCount(4, 4).c, 0);
  assert.equal(criticalCount(5, 5).c, 2);
  assert.equal(criticalCount(3, 3).method, "exact");
});

test("exactInterval: three runs a side never exclude zero, even when every after run is faster", () => {
  const iv = exactInterval([600, 610, 620], [300, 310, 320]);
  assert.equal(iv.lo, Number.NEGATIVE_INFINITY);
  assert.equal(iv.hi, Number.POSITIVE_INFINITY);
});

test("exactInterval: four a side excludes zero only when all 16 pairs agree", () => {
  const all = exactInterval([600, 610, 620, 630], [300, 310, 320, 330]);
  assert.ok(all.hi < 0, "every after run beats every before run");
  const one = exactInterval([600, 610, 620, 630], [300, 310, 320, 615]);
  assert.ok(one.hi >= 0, "one overlapping pair is enough to keep zero inside");
});

test("exactInterval: five a side tolerates two disagreeing pairs", () => {
  // after = 300..340 against before = 600..640 except one after run at 605: it beats 1 before run... 4 pairs agree less; count: 605 vs 600 is slower (1 pair disagrees)
  const iv = exactInterval([600, 610, 620, 630, 640], [300, 310, 320, 330, 605]);
  assert.ok(iv.hi < 0, "one disagreeing pair of 25 still rules out no change at 5 a side");
  assert.equal(iv.estimate < 0, true);
  const worse = exactInterval([600, 610, 620, 630, 640], [300, 310, 320, 625, 635]);
  assert.ok(worse.hi >= 0, "five disagreeing pairs do not");
});

test("exactInterval: the estimate is the median of every after-minus-before difference", () => {
  const iv = exactInterval([10, 20], [15, 25]);
  // differences: 5, 15, -5, 5 -> sorted -5, 5, 5, 15 -> median 5
  assert.equal(iv.estimate, 5);
});

test("large samples use the normal approximation and say so", () => {
  const before = Array.from({ length: 80 }, (_, i) => 600 + (i % 7));
  const after = Array.from({ length: 80 }, (_, i) => 500 + (i % 7));
  const iv = exactInterval(before, after);
  assert.equal(iv.method, "normal-approximation");
  assert.ok(iv.hi < 0);
});

test("fisherOneSided and the failure threshold", () => {
  assert.ok(fisherOneSided(0, 5, 0, 5) > 0.99, "no failures anywhere is no evidence");
  assert.ok(fisherOneSided(0, 5, 5, 5) < 0.01);
  // five runs before with no failure, five after: the fewest failures that count as more than chance
  const t = failedAfterThreshold(0, 5, 5);
  assert.ok(t !== null && t >= 1 && t <= 5);
  assert.ok(fisherOneSided(0, 5, t!, 5) <= 0.05);
  assert.ok(fisherOneSided(0, 5, t! - 1, 5) > 0.05);
});

test("selectSamples keeps comparable runs and counts failures; skipped and cancelled say nothing", () => {
  const runs: LedgerRun[] = [
    run(1, day(10), 300),
    run(2, day(10, 11), 310),
    run(3, day(10, 12), 5, { conclusion: "failure" }),
    run(4, day(10, 13), null, { conclusion: "skipped" }),
    run(5, day(10, 14), 280, { conclusion: "cancelled" }),
    run(6, day(10, 15), 300, { event: "push" }),
    run(7, day(20), 200),
  ];
  const o = { job: "test", event: "pull_request", metric: "job" as const, before: { from: day(1), to: day(15) }, after: { from: day(15), to: day(30) } };
  const { before, after } = selectSamples(runs, o);
  assert.deepEqual(before.seconds, [300, 310]);
  assert.equal(before.finished, 3);
  assert.equal(before.failed, 1);
  assert.deepEqual(after.seconds, [200]);
});

test("selectSamples refuses to mix runners or workflows silently", () => {
  const runs = [run(1, day(10), 300, { label: "ubuntu-latest" }), run(2, day(20), 120, { label: "celesto-micro" })];
  const o = { job: "test", event: "pull_request", metric: "job" as const, before: { from: day(1), to: day(15) }, after: { from: day(15), to: day(30) } };
  assert.throws(() => selectSamples(runs, o), /ran on different runners.*--label/);
  const ok = selectSamples(runs, { ...o, label: "celesto-micro" });
  assert.equal(ok.before.seconds.length, 0);
  assert.deepEqual(ok.after.seconds, [120]);
  const two = [run(1, day(10), 300, { workflow: "CI" }), run(2, day(20), 300, { workflow: "Nightly" })];
  assert.throws(() => selectSamples(two, o), /several workflows/);
  assert.throws(() => selectSamples([], { ...o, job: undefined }), /--job is required/);
  assert.throws(() => selectSamples(two, { ...o, job: "nope" }), CompareError);
  assert.throws(() => selectSamples(two, { ...o, metric: "wall" }), /needs --workflow/);
});

test("compareSamples: faster, slower, no change, mixed and too few", () => {
  const sample = (secs: number[], failed = 0) => ({ seconds: secs, finished: secs.length + failed, failed, firstAt: null, lastAt: null });
  const span = { before: 5, after: 5 };
  const faster = compareSamples(sample([600, 610, 620, 630, 640]), sample([300, 310, 320, 330, 340]), span);
  assert.equal(faster.verdict, "median faster");
  const slower = compareSamples(sample([300, 310, 320, 330, 340]), sample([600, 610, 620, 630, 640]), span);
  assert.equal(slower.verdict, "median slower");
  const same = compareSamples(sample([300, 310, 320, 330, 340]), sample([305, 315, 318, 322, 345]), span);
  assert.equal(same.verdict, "no measurable change yet");
  assert.match(same.notes.join(" "), /again and again/);
  const few = compareSamples(sample([300, 310, 320, 330]), sample([100, 110, 120, 130, 140]), span);
  assert.equal(few.verdict, "not enough runs yet");
  assert.equal(few.interval, null);
  assert.throws(() => compareSamples(sample([1, 2, 3, 4, 5]), sample([1, 2, 3, 4, 5]), span, 3), /fewest/);
});

test("compareSamples: more failures after than chance explains makes the speed-up invalid", () => {
  const before = { seconds: [600, 610, 620, 630, 640], finished: 5, failed: 0, firstAt: null, lastAt: null };
  const after = { seconds: [300, 310, 320, 330, 340], finished: 12, failed: 7, firstAt: null, lastAt: null };
  const c = compareSamples(before, after, { before: 5, after: 5 });
  assert.equal(c.verdict, "not valid: more runs failed after");
  assert.match(c.notes.join(" "), /fails early looks fast/);
  // 6 failed of 11 is p = 0.058: more than before, but within chance, so it is a note and not a veto
  const near = compareSamples(before, { ...after, finished: 11, failed: 6 }, { before: 5, after: 5 });
  assert.equal(near.verdict, "median faster");
  assert.match(near.notes.join(" "), /within chance/);
});

test("compareSamples notes a window under a day, and the slowest 5% below 20 runs", () => {
  const s = (secs: number[]) => ({ seconds: secs, finished: secs.length, failed: 0, firstAt: null, lastAt: null });
  const c = compareSamples(s([600, 610, 620, 630, 640]), s([300, 310, 320, 330, 340]), { before: 3, after: 0.2 });
  const n = c.notes.join(" ");
  assert.match(n, /shorter than a day/);
  assert.match(n, /Below 20 runs/);
  assert.equal(c.slowestIsMax, true);
  assert.equal(c.slowestAfter, 340);
});

test("renderComparison prints the counts, the interval and the verdict", () => {
  const before = { seconds: [600, 610, 620, 630, 640], finished: 5, failed: 0, firstAt: null, lastAt: null };
  const after = { seconds: [300, 310, 320, 330, 340], finished: 5, failed: 0, firstAt: null, lastAt: null };
  const c = compareSamples(before, after, { before: 5, after: 5 });
  const text = renderComparison(c, { job: "test", event: "pull_request", metric: "job", before: { from: day(1), to: day(10) }, after: { from: day(10), to: day(20) } });
  assert.match(text, /before .*: 5 runs, median 10m 20s/);
  assert.match(text, /after .*: 5 runs, median 5m 20s/);
  assert.match(text, /verdict: median faster \(5 before, 5 after\)/);
  assert.match(text, /exact 95% interval/);
});

test("settledProblem: fast runs finish first, so an unsettled window is refused", () => {
  const w = { before: { from: "2026-11-01T00:00:00Z", to: "2026-11-10T00:00:00Z" }, after: { from: "2026-11-10T00:00:00Z", to: "2026-11-12T00:00:00Z" } };
  const now = new Date("2026-11-20T00:00:00Z");
  const good = { pulledAt: "2026-11-19T00:00:00Z", since: "2026-11-01", workflow: null };
  assert.equal(settledProblem({ state: good, ...w, now, settleHours: 2, assumeSettled: false }), null);
  assert.match(settledProblem({ state: good, ...w, now: new Date("2026-11-12T01:00:00Z"), settleHours: 2, assumeSettled: true })!, /less than 2 h ago/, "even --assume-settled cannot skip the time rule");
  assert.match(settledProblem({ state: null, ...w, now, settleHours: 2, assumeSettled: false })!, /no record of when this ledger was pulled/);
  assert.equal(settledProblem({ state: null, ...w, now, settleHours: 2, assumeSettled: true }), null);
  assert.match(settledProblem({ state: { ...good, pulledAt: "2026-11-12T01:00:00Z" }, ...w, now, settleHours: 2, assumeSettled: false })!, /before the after window had settled/);
  assert.match(settledProblem({ state: { ...good, since: "2026-11-05" }, ...w, now, settleHours: 2, assumeSettled: false })!, /Pull again with an earlier --since/);
});
