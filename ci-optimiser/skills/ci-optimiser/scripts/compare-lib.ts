/**
 * Before / after comparison of CI timings: the pure half of `ledger.ts compare`.
 *
 * SELF-CONTAINED like ledger-lib.ts: plain Node, no installs, no imports
 * outside this folder.
 *
 * WHY THIS EXISTS
 *
 * "Keep the change if it saved time" needs a verdict that is not a guess. CI
 * times vary from run to run, so one run cannot separate a change from noise.
 * The verdict here comes from the Hodges-Lehmann estimate of how far times moved
 * (the median of every after-minus-before difference) and its exact 95%
 * confidence interval from the Mann-Whitney rank test (Bauer, 1972). The exact
 * interval keeps its 95% at any run count and for any shape of times; a
 * bootstrap interval is only an approximation and has no guarantee at 5 runs.
 *
 * WHY 5 RUNS A SIDE IS THE FLOOR (arithmetic you can check)
 *
 * With 3 runs a side there are C(6,3) = 20 ways to order the runs, and "every
 * after run beats every before run" happens by chance 1 time in 20. A 95%
 * two-sided interval allows 1 in 40 on each side, so no 3-run result can rule
 * out "no change". With 4 a side it can, but only when all 16 pairs agree. With
 * 5 a side, 2 of the 25 pairs may disagree, which leaves room for ordinary
 * noise. `exactInterval` computes this, so the floor is not a rule of thumb.
 *
 * WHAT THE 95% DOES NOT COVER
 *
 * It assumes each run is an independent draw. Runs that share one busy hour or
 * one slow runner pool move together, so five of them are worth less than five
 * spread out. A window shorter than a day is flagged. And the 95% holds for one
 * look at a window chosen before looking: running `compare` again and again
 * until it says "faster" is not allowed (SKILL.md, rules).
 */
import { type LedgerRun, quantile } from "./ledger-lib.ts";

export const MIN_RUNS = 5;
/** Beyond this many pairs the exact table gets slow, so a normal approximation is used and named. */
const EXACT_PAIR_LIMIT = 4000;
const Z_95 = 1.959964;

export interface Interval {
  /** Median of every (after − before) difference. Negative means faster. */
  estimate: number;
  lo: number;
  hi: number;
  method: "exact" | "normal-approximation";
  /** Pairs that may disagree with the verdict direction before zero is back inside the interval (0 when it cannot rule out zero). */
  slack: number;
}

/**
 * P(U ≤ k) for k = 0..max, where U counts pairs (after, before) with after > before
 * under "no change", for sizes m (after) and n (before). Built from the recursion on the
 * largest observation: it is in the after group with probability m/(m+n) and then beats all n.
 */
function uCdf(m: number, n: number, max: number): number[] {
  // prev[j][k] = P for sizes (i-1, j); cur[j][k] = P for sizes (i, j)
  let prev: Float64Array[] = Array.from({ length: n + 1 }, () => {
    const a = new Float64Array(max + 1);
    a[0] = 1;
    return a;
  });
  for (let i = 1; i <= m; i++) {
    const cur: Float64Array[] = [];
    for (let j = 0; j <= n; j++) {
      const a = new Float64Array(max + 1);
      if (j === 0) a[0] = 1;
      else {
        const wi = i / (i + j);
        const wj = j / (i + j);
        for (let k = 0; k <= max; k++) {
          const fromAfter = k - j >= 0 ? prev[j]![k - j]! : 0;
          a[k] = wi * fromAfter + wj * cur[j - 1]![k]!;
        }
      }
      cur.push(a);
    }
    prev = cur;
  }
  const pmf = prev[n]!;
  const out: number[] = [];
  let acc = 0;
  for (let k = 0; k <= max; k++) {
    acc += pmf[k]!;
    out.push(acc);
  }
  return out;
}

/** The largest c with P(U ≤ c) ≤ alpha/2, or −1 when even P(U = 0) is above it (no interval can rule out zero). */
export function criticalCount(m: number, n: number, alpha = 0.05): { c: number; method: Interval["method"] } {
  if (m * n <= EXACT_PAIR_LIMIT) {
    const cdf = uCdf(m, n, Math.floor((m * n) / 2));
    let c = -1;
    for (let k = 0; k < cdf.length; k++) {
      if (cdf[k]! <= alpha / 2 + 1e-12) c = k;
      else break;
    }
    return { c, method: "exact" };
  }
  const mean = (m * n) / 2;
  const sd = Math.sqrt((m * n * (m + n + 1)) / 12);
  return { c: Math.floor(mean - Z_95 * sd - 0.5), method: "normal-approximation" };
}

/** Hodges-Lehmann estimate and its distribution-free interval for the shift from `before` to `after`. */
export function exactInterval(before: number[], after: number[], alpha = 0.05): Interval {
  const m = after.length;
  const n = before.length;
  const diffs: number[] = [];
  for (const a of after) for (const b of before) diffs.push(a - b);
  diffs.sort((x, y) => x - y);
  const mn = diffs.length;
  const estimate = mn % 2 ? diffs[(mn - 1) / 2]! : (diffs[mn / 2 - 1]! + diffs[mn / 2]!) / 2;
  const { c, method } = criticalCount(m, n, alpha);
  const lo = c >= 0 ? diffs[c]! : Number.NEGATIVE_INFINITY;
  const hi = c >= 0 ? diffs[mn - c - 1]! : Number.POSITIVE_INFINITY;
  return { estimate, lo, hi, method, slack: Math.max(c, 0) };
}

/** log(n!) by summation: counts here are small. */
function logFactorial(n: number): number {
  let s = 0;
  for (let i = 2; i <= n; i++) s += Math.log(i);
  return s;
}
function logChoose(n: number, k: number): number {
  return k < 0 || k > n ? Number.NEGATIVE_INFINITY : logFactorial(n) - logFactorial(k) - logFactorial(n - k);
}

/**
 * One-sided Fisher exact test: the chance of at least `failedAfter` failures in the after group
 * if failures were spread over both groups at random, given the totals.
 */
export function fisherOneSided(failedBefore: number, finishedBefore: number, failedAfter: number, finishedAfter: number): number {
  const total = finishedBefore + finishedAfter;
  const failed = failedBefore + failedAfter;
  let p = 0;
  for (let x = failedAfter; x <= Math.min(failed, finishedAfter); x++) {
    if (failed - x > finishedBefore) continue;
    p += Math.exp(logChoose(failed, x) + logChoose(total - failed, finishedAfter - x) - logChoose(total, finishedAfter));
  }
  return Math.min(1, p);
}

/** The fewest failed runs after (with the same failures before) that would count as more than chance. */
export function failedAfterThreshold(failedBefore: number, finishedBefore: number, finishedAfter: number): number | null {
  for (let x = 0; x <= finishedAfter; x++) {
    if (fisherOneSided(failedBefore, finishedBefore, x, finishedAfter) <= 0.05) return x;
  }
  return null;
}

// ── Choosing comparable runs ──────────────────────────────────────────────

export interface Window {
  from: string;
  to: string;
}

export interface CompareOptions {
  /** A job name, for metric "job". */
  job?: string;
  /** A workflow name: required for metric "wall", and to pick between workflows that share a job name. */
  workflow?: string;
  /** A runner label that the job's `labels` must include. */
  label?: string;
  event: string;
  branch?: string;
  metric: "job" | "wall";
  before: Window;
  after: Window;
}

export interface Sample {
  /** Seconds of each successful, comparable run. */
  seconds: number[];
  /** Runs that finished as success or failure (the failure-rate denominator). */
  finished: number;
  failed: number;
  firstAt: string | null;
  lastAt: string | null;
}

export class CompareError extends Error {}

function inWindow(r: LedgerRun, w: Window): boolean {
  return r.createdAt >= w.from && r.createdAt < w.to;
}

/** Runs of the same workflow, trigger and branch: the "comparable" set both sides draw from. */
function candidateRuns(runs: LedgerRun[], o: CompareOptions): LedgerRun[] {
  return runs.filter((r) => r.event === o.event && (!o.branch || r.branch === o.branch) && (!o.workflow || r.workflow === o.workflow));
}

export function selectSamples(runs: LedgerRun[], o: CompareOptions): { before: Sample; after: Sample } {
  if (o.metric === "job" && !o.job) throw new CompareError("--job is required (a job name from the report), or use --metric wall with --workflow");
  if (o.metric === "wall" && !o.workflow) throw new CompareError("--metric wall needs --workflow (the run's wall time is only comparable inside one workflow)");
  const pool = candidateRuns(runs, o).filter((r) => inWindow(r, o.before) || inWindow(r, o.after));

  if (o.metric === "job") {
    const names = new Set<string>();
    const labelSets = new Set<string>();
    for (const r of pool) {
      for (const j of r.jobs) {
        if (j.name !== o.job) continue;
        names.add(r.workflow);
        labelSets.add([...j.labels].sort().join(","));
      }
    }
    if (names.size === 0) throw new CompareError(`no job "${o.job}" in ${o.event} runs in either window`);
    if (names.size > 1 && !o.workflow) throw new CompareError(`job "${o.job}" exists in several workflows (${[...names].join(", ")}): pass --workflow`);
    if (labelSets.size > 1 && !o.label) {
      throw new CompareError(`job "${o.job}" ran on different runners (${[...labelSets].map((s) => s || "no label").join(" | ")}): pass --label so both sides time the same machine`);
    }
  }

  const take = (w: Window): Sample => {
    const out: Sample = { seconds: [], finished: 0, failed: 0, firstAt: null, lastAt: null };
    for (const r of pool.filter((x) => inWindow(x, w))) {
      let secs: number | null = null;
      let conclusion: string | null = null;
      if (o.metric === "wall") {
        conclusion = r.conclusion;
        secs = r.wallSeconds;
      } else {
        const j = r.jobs.find((x) => x.name === o.job && (!o.label || x.labels.includes(o.label)));
        if (!j) continue;
        conclusion = j.conclusion;
        secs = j.seconds;
      }
      if (conclusion !== "success" && conclusion !== "failure") continue; // skipped and cancelled say nothing about speed or failure
      out.finished += 1;
      if (conclusion === "failure") out.failed += 1;
      if (conclusion === "success" && secs !== null) out.seconds.push(secs);
      out.firstAt = out.firstAt === null || r.createdAt < out.firstAt ? r.createdAt : out.firstAt;
      out.lastAt = out.lastAt === null || r.createdAt > out.lastAt ? r.createdAt : out.lastAt;
    }
    return out;
  };
  return { before: take(o.before), after: take(o.after) };
}

// ── The verdict ───────────────────────────────────────────────────────────

export type Verdict = "median faster" | "median slower" | "mixed" | "no measurable change yet" | "not enough runs yet" | "not valid: more runs failed after";

export interface Comparison {
  verdict: Verdict;
  runsBefore: number;
  runsAfter: number;
  medianBefore: number | null;
  medianAfter: number | null;
  /** The slowest run below 20 runs, else the slowest 5% (p95). */
  slowestBefore: number | null;
  slowestAfter: number | null;
  slowestIsMax: boolean;
  interval: Interval | null;
  failures: { before: string; after: string; pValue: number; beyondChance: boolean; threshold: number | null };
  notes: string[];
}

function slowest(values: number[]): { v: number | null; isMax: boolean } {
  if (values.length === 0) return { v: null, isMax: false };
  return values.length < 20 ? { v: Math.max(...values), isMax: true } : { v: quantile(values, 0.95), isMax: false };
}

export function compareSamples(before: Sample, after: Sample, spanDays: { before: number; after: number }, minRuns = MIN_RUNS): Comparison {
  if (minRuns < MIN_RUNS) throw new CompareError(`--min-runs: ${MIN_RUNS} is the fewest a 95% interval can use`);
  const notes: string[] = [];
  const sb = slowest(before.seconds);
  const sa = slowest(after.seconds);
  const pValue = fisherOneSided(before.failed, before.finished, after.failed, after.finished);
  const beyondChance = after.failed > 0 && pValue <= 0.05;
  const base: Comparison = {
    verdict: "not enough runs yet",
    runsBefore: before.seconds.length,
    runsAfter: after.seconds.length,
    medianBefore: quantile(before.seconds, 0.5),
    medianAfter: quantile(after.seconds, 0.5),
    slowestBefore: sb.v,
    slowestAfter: sa.v,
    slowestIsMax: sb.isMax || sa.isMax,
    interval: null,
    failures: {
      before: `${before.failed} of ${before.finished}`,
      after: `${after.failed} of ${after.finished}`,
      pValue,
      beyondChance,
      threshold: failedAfterThreshold(before.failed, before.finished, after.finished),
    },
    notes,
  };
  if (before.seconds.length < minRuns || after.seconds.length < minRuns) {
    notes.push(`Needs at least ${minRuns} successful comparable runs a side (${before.seconds.length} before, ${after.seconds.length} after). Choose a longer window, or wait. Never start runs just to fill the count: runs cost money.`);
    return base;
  }
  const iv = exactInterval(before.seconds, after.seconds);
  base.interval = iv;
  const mb = base.medianBefore!;
  const ma = base.medianAfter!;
  const excludesZero = iv.lo > 0 || iv.hi < 0;
  if (!excludesZero) base.verdict = "no measurable change yet";
  else if (iv.hi < 0 && ma < mb) base.verdict = "median faster";
  else if (iv.lo > 0 && ma > mb) base.verdict = "median slower";
  else base.verdict = "mixed";
  if (iv.method === "normal-approximation") notes.push("Large samples: the interval uses a normal approximation of the rank test, not the exact table.");
  if (before.seconds.length < 20 || after.seconds.length < 20) notes.push("Below 20 runs on a side the slowest 5% is just the slowest run: provisional.");
  if (spanDays.after < 1 || spanDays.before < 1) notes.push("A window shorter than a day: runs that share one busy hour or one runner pool move together, so they are worth fewer than their count. Let the after window cover more than a day when you can.");
  if (base.verdict === "no measurable change yet") notes.push("The change may be real but smaller than the run-to-run noise at this count. Do not run `compare` again and again until it says faster: a second look at a count chosen after seeing the first is exploratory, and must be reported as such beside the first.");
  if (base.verdict === "mixed") notes.push("The interval excludes zero but the median moved the other way or not at all (a change that makes most runs faster and the middle one slower, or one that only reshapes the spread). Report both numbers. Do not call it faster.");
  if (after.failed > before.failed && !beyondChance) notes.push("More runs failed after than before, but within chance: at a few runs a side the test cannot rule out a real rise. Name the cause of each failure before calling the change faster.");
  if (beyondChance) {
    base.verdict = "not valid: more runs failed after";
    notes.push("More runs failed after than chance explains, so the timings cannot be read as a speed-up: a run that fails early looks fast. Find the cause of the failures first.");
  }
  return base;
}

// ── Settled windows ───────────────────────────────────────────────────────

export interface PullState {
  pulledAt: string;
  /** The oldest day the pull covered (YYYY-MM-DD). */
  since: string;
  /** The workflow file the pull was limited to, or null for all. */
  workflow: string | null;
}

/**
 * Fast runs finish first. A window read while runs are still going holds only the quick ones, so a
 * "faster" verdict can appear with no change at all. A comparison is allowed only when the ledger
 * was pulled after the after window ended, with time left for stragglers to finish.
 * Returns the reason to refuse, or null when the windows are settled.
 */
export function settledProblem(opts: { state: PullState | null; before: Window; after: Window; now: Date; settleHours: number; assumeSettled: boolean }): string | null {
  const settleMs = opts.settleHours * 3_600_000;
  const afterEnd = Date.parse(opts.after.to);
  if (opts.now.getTime() < afterEnd + settleMs) {
    return `the after window ends ${opts.after.to}, less than ${opts.settleHours} h ago: runs created in it may still be going, and the fast ones finish first. Wait, or end the window earlier.`;
  }
  if (opts.assumeSettled) return null;
  if (!opts.state) {
    return "no record of when this ledger was pulled (it is written by `pull`, in the report folder). Run `ledger.ts pull --since <date before the before window>` now, then compare. For a ledger made with `import`, pass --assume-settled once you know every run in both windows had finished.";
  }
  if (Date.parse(opts.state.pulledAt) < afterEnd + settleMs) {
    return `the ledger was last pulled ${opts.state.pulledAt}, before the after window had settled (it ended ${opts.after.to}, plus ${opts.settleHours} h). Pull again, then compare.`;
  }
  const beforeDay = opts.before.from.slice(0, 10);
  if (opts.state.since > beforeDay) {
    return `the last pull started at ${opts.state.since}, after the before window began (${beforeDay}). Pull again with an earlier --since.`;
  }
  return null;
}

// ── Output ────────────────────────────────────────────────────────────────

function dur(s: number | null): string {
  if (s === null) return "—";
  const r = Math.round(s);
  return r >= 60 ? `${Math.floor(r / 60)}m ${String(r % 60).padStart(2, "0")}s` : `${r}s`;
}
function signedDur(s: number): string {
  if (!Number.isFinite(s)) return s < 0 ? "−∞" : "+∞";
  return `${s < 0 ? "−" : "+"}${dur(Math.abs(s))}`;
}

export function renderComparison(c: Comparison, o: CompareOptions): string {
  const what = o.metric === "job" ? `job "${o.job}"${o.label ? ` on ${o.label}` : ""}` : `workflow "${o.workflow}" wall time`;
  const slowLabel = c.slowestIsMax ? "slowest run" : "slowest 5%";
  const lines = [
    `# Before / after: ${what}`,
    "",
    `${o.event} runs${o.branch ? ` on ${o.branch}` : ""}. Times are for runs that passed; skipped and cancelled runs are left out.`,
    "",
    `before ${o.before.from.slice(0, 16)}..${o.before.to.slice(0, 16)}: ${c.runsBefore} runs, median ${dur(c.medianBefore)}, ${slowLabel} ${dur(c.slowestBefore)}`,
    `after  ${o.after.from.slice(0, 16)}..${o.after.to.slice(0, 16)}: ${c.runsAfter} runs, median ${dur(c.medianAfter)}, ${slowLabel} ${dur(c.slowestAfter)}`,
  ];
  if (c.interval) {
    lines.push(
      `shift (Hodges-Lehmann, ${c.interval.method} 95% interval): ${signedDur(c.interval.estimate)}, from ${signedDur(c.interval.lo)} to ${signedDur(c.interval.hi)}`,
    );
  }
  lines.push(
    `failed runs: before ${c.failures.before}, after ${c.failures.after}` +
      (c.failures.threshold !== null ? ` (more than chance from ${c.failures.threshold} failed after)` : ""),
    "",
    `verdict: ${c.verdict} (${c.runsBefore} before, ${c.runsAfter} after)`,
  );
  if (c.notes.length) lines.push("", ...c.notes.map((n) => `- ${n}`));
  return lines.join("\n");
}
