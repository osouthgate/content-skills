/**
 * CI ledger: the pure half of the ci-optimiser skill's scripts. `ledger.ts`
 * fetches from the GitHub API and touches the disk; everything here is a
 * function of its inputs, so it is tested with recorded API responses.
 *
 * SELF-CONTAINED ON PURPOSE. These scripts ship inside the skill folder and
 * run with plain `node` (Node 22.18+ strips TypeScript types itself): no
 * `tsx`, no `zod`, no imports outside this folder. So the skill can be copied
 * into another repository and work there. Boundary checks are hand-written
 * type guards for the same reason.
 *
 * WHY A LEDGER
 *
 * "Is CI getting faster?" had no answer that survived a week. GitHub's run
 * history expires and cannot be joined to a commit range. The ledger keeps one
 * line per completed workflow run in `<ledger dir>/<YYYY-MM-DD>.jsonl`: the
 * commit it ran on, the pull request, the trigger, the wall and queue time,
 * every job's time and runner, and the steps worth looking at. With history in
 * the repo, a change that made CI slower or faster is found by commit, not by
 * memory.
 *
 * ONE FILE PER DAY, KEYED BY RUN
 *
 * One line per `runId:attempt`, sorted by creation time. A pull merges by key,
 * so pulling twice, or two people pulling the same day, produces the same
 * bytes: nothing to resolve.
 */

// ── Small guards (no dependencies) ────────────────────────────────────────

type Obj = Record<string, unknown>;

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function str(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}
function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function strArr(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}
/** An ISO-8601 datetime with a zone. The day file's name is built from it, so free text is refused. */
function isoDateTime(v: unknown): string | null {
  return typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/.test(v) ? v : null;
}

// ── Raw GitHub shapes (checked at the boundary) ───────────────────────────

export interface RawStep {
  name: string;
  conclusion: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface RawJob {
  id: number;
  name: string;
  conclusion: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  runner_name?: string | null;
  labels: string[];
  steps: RawStep[];
}

export interface RawRun {
  id: number;
  name: string | null;
  display_title: string | null;
  path: string | null;
  run_attempt: number;
  event: string;
  conclusion: string | null;
  head_branch: string | null;
  head_sha: string;
  head_commit_message: string | null;
  pull_requests: number[];
  created_at: string;
  run_started_at: string | null;
  updated_at: string | null;
  html_url: string | null;
}

function toRawRun(v: unknown): RawRun | null {
  if (!isObj(v)) return null;
  const id = num(v.id);
  const event = str(v.event);
  const sha = str(v.head_sha);
  const created = isoDateTime(v.created_at);
  if (id === null || event === null || sha === null || created === null) return null;
  const prs = Array.isArray(v.pull_requests)
    ? v.pull_requests
        .map((p) => (typeof p === "number" ? p : isObj(p) ? num(p.number) : null))
        .filter((n): n is number => n !== null)
    : [];
  return {
    id,
    name: str(v.name),
    display_title: str(v.display_title),
    path: str(v.path),
    run_attempt: num(v.run_attempt) ?? 1,
    event,
    conclusion: str(v.conclusion),
    head_branch: str(v.head_branch),
    head_sha: sha,
    head_commit_message: isObj(v.head_commit) ? str(v.head_commit.message) : null,
    pull_requests: prs,
    created_at: created,
    run_started_at: isoDateTime(v.run_started_at),
    updated_at: isoDateTime(v.updated_at),
    html_url: str(v.html_url),
  };
}

function toRawJob(v: unknown): RawJob | null {
  if (!isObj(v)) return null;
  const id = num(v.id);
  const name = str(v.name);
  if (id === null || name === null) return null;
  const steps = Array.isArray(v.steps)
    ? v.steps.flatMap((s): RawStep[] => {
        if (!isObj(s) || str(s.name) === null) return [];
        return [{ name: str(s.name)!, conclusion: str(s.conclusion), started_at: isoDateTime(s.started_at), completed_at: isoDateTime(s.completed_at) }];
      })
    : [];
  return {
    id,
    name,
    conclusion: str(v.conclusion),
    created_at: isoDateTime(v.created_at),
    started_at: isoDateTime(v.started_at),
    completed_at: isoDateTime(v.completed_at),
    runner_name: str(v.runner_name),
    labels: strArr(v.labels),
    steps,
  };
}

export function parseRuns(body: unknown): RawRun[] {
  if (!isObj(body) || !Array.isArray(body.workflow_runs)) throw new Error("GitHub runs response: no workflow_runs array");
  return body.workflow_runs.map(toRawRun).filter((r): r is RawRun => r !== null);
}

export function parseJobs(body: unknown): RawJob[] {
  if (!isObj(body) || !Array.isArray(body.jobs)) throw new Error("GitHub jobs response: no jobs array");
  return body.jobs.map(toRawJob).filter((j): j is RawJob => j !== null);
}

// ── Ledger shape ──────────────────────────────────────────────────────────

export interface LedgerStep {
  name: string;
  seconds: number;
  conclusion: string | null;
}

export interface LedgerJob {
  name: string;
  conclusion: string | null;
  runner: string | null;
  labels: string[];
  /** Started → completed. Null when the job never started (skipped). */
  seconds: number | null;
  /** Created → started: time spent waiting for a runner. */
  queueSeconds: number | null;
  /** Only steps at or over the step floor, to keep lines short. */
  steps: LedgerStep[];
}

export interface LedgerRun {
  v: 1;
  key: string;
  runId: number;
  attempt: number;
  workflow: string;
  path: string | null;
  event: string;
  branch: string | null;
  sha: string;
  prs: number[];
  /** First line of the run title or head commit message. */
  title: string;
  conclusion: string | null;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  /** Run start → last job completed. */
  wallSeconds: number | null;
  /** Run created → first job started. */
  queueSeconds: number | null;
  /** Sum of every job's seconds: the runner time the run cost. */
  jobSeconds: number;
  jobs: LedgerJob[];
  url: string | null;
}

function toLedgerJob(v: unknown): LedgerJob | null {
  if (!isObj(v) || str(v.name) === null || !Array.isArray(v.steps)) return null;
  const steps: LedgerStep[] = [];
  for (const s of v.steps) {
    if (!isObj(s) || str(s.name) === null || num(s.seconds) === null) return null;
    steps.push({ name: str(s.name)!, seconds: num(s.seconds)!, conclusion: str(s.conclusion) });
  }
  return {
    name: str(v.name)!,
    conclusion: str(v.conclusion),
    runner: str(v.runner),
    labels: strArr(v.labels),
    seconds: num(v.seconds),
    queueSeconds: num(v.queueSeconds),
    steps,
  };
}

/** A ledger line read back from disk, checked field by field. */
function toLedgerRun(v: unknown): LedgerRun | null {
  if (!isObj(v) || v.v !== 1) return null;
  const key = str(v.key);
  const runId = num(v.runId);
  const attempt = num(v.attempt);
  const workflow = str(v.workflow);
  const event = str(v.event);
  const sha = str(v.sha);
  const createdAt = isoDateTime(v.createdAt);
  const jobSeconds = num(v.jobSeconds);
  if (key === null || runId === null || attempt === null || workflow === null || event === null || sha === null || createdAt === null || jobSeconds === null || !Array.isArray(v.jobs)) return null;
  const jobs: LedgerJob[] = [];
  for (const j of v.jobs) {
    const job = toLedgerJob(j);
    if (!job) return null;
    jobs.push(job);
  }
  return {
    v: 1,
    key,
    runId,
    attempt,
    workflow,
    path: str(v.path),
    event,
    branch: str(v.branch),
    sha,
    prs: Array.isArray(v.prs) ? v.prs.filter((p): p is number => typeof p === "number") : [],
    title: str(v.title) ?? "",
    conclusion: str(v.conclusion),
    createdAt,
    startedAt: str(v.startedAt),
    completedAt: str(v.completedAt),
    wallSeconds: num(v.wallSeconds),
    queueSeconds: num(v.queueSeconds),
    jobSeconds,
    jobs,
    url: str(v.url),
  };
}

export const STEP_FLOOR_SECONDS = 30;

function seconds(from: string | null | undefined, to: string | null | undefined): number | null {
  if (!from || !to) return null;
  const s = (Date.parse(to) - Date.parse(from)) / 1000;
  return Number.isFinite(s) && s >= 0 ? Math.round(s) : null;
}

function firstLine(text: string | null | undefined): string {
  return (text ?? "").split("\n")[0]!.trim().slice(0, 160);
}

export function runKey(runId: number, attempt: number): string {
  return `${runId}:${attempt}`;
}

/** One completed run and its jobs, as one ledger line. */
export function normaliseRun(run: RawRun, jobs: RawJob[], stepFloor = STEP_FLOOR_SECONDS): LedgerRun {
  const attempt = run.run_attempt;
  const ledgerJobs: LedgerJob[] = jobs.map((j) => ({
    name: j.name,
    conclusion: j.conclusion ?? null,
    runner: j.runner_name ?? null,
    labels: j.labels,
    seconds: seconds(j.started_at, j.completed_at),
    queueSeconds: seconds(j.created_at, j.started_at),
    steps: j.steps
      .map((s) => ({ name: s.name, seconds: seconds(s.started_at, s.completed_at), conclusion: s.conclusion ?? null }))
      .filter((s): s is LedgerStep => s.seconds !== null && s.seconds >= stepFloor),
  }));
  const started = jobs.map((j) => j.started_at).filter((t): t is string => Boolean(t)).sort();
  const completed = jobs.map((j) => j.completed_at).filter((t): t is string => Boolean(t)).sort();
  const runStart = run.run_started_at ?? run.created_at;
  const lastDone = completed.at(-1) ?? run.updated_at ?? null;
  return {
    v: 1,
    key: runKey(run.id, attempt),
    runId: run.id,
    attempt,
    workflow: run.name ?? run.path ?? "unknown",
    path: run.path ?? null,
    event: run.event,
    branch: run.head_branch ?? null,
    sha: run.head_sha,
    prs: [...run.pull_requests].sort((a, b) => a - b),
    title: firstLine(run.display_title ?? run.head_commit_message),
    conclusion: run.conclusion ?? null,
    createdAt: run.created_at,
    startedAt: run.run_started_at ?? null,
    completedAt: lastDone,
    wallSeconds: seconds(runStart, lastDone),
    queueSeconds: seconds(run.created_at, started[0]),
    jobSeconds: ledgerJobs.reduce((a, j) => a + (j.seconds ?? 0), 0),
    jobs: ledgerJobs,
    url: run.html_url ?? null,
  };
}

// ── Day files ─────────────────────────────────────────────────────────────

const DAY = /^\d{4}-\d{2}-\d{2}$/;

/** The day file a run belongs to. Refuses anything but YYYY-MM-DD: the result becomes a file name. */
export function dayOf(run: Pick<LedgerRun, "createdAt">): string {
  const day = run.createdAt.slice(0, 10);
  if (!DAY.test(day)) throw new Error(`ci-ledger: run createdAt "${run.createdAt}" is not an ISO date`);
  return day;
}

/** Parse a day file. A line that is not a ledger run is an error, not skipped: the file is ours. */
export function parseDay(text: string, label: string): LedgerRun[] {
  const out: LedgerRun[] = [];
  for (const [i, line] of text.split("\n").entries()) {
    if (line.trim() === "") continue;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line) as unknown;
    } catch {
      throw new Error(`${label}:${i + 1}: not valid JSON`);
    }
    const run = toLedgerRun(parsed);
    if (!run) throw new Error(`${label}:${i + 1}: not a ledger run`);
    out.push(run);
  }
  return out;
}

/** Merge runs into a day's lines by key (a newer copy of a key replaces the older), sorted by time then key. */
export function mergeDay(existing: LedgerRun[], incoming: LedgerRun[]): LedgerRun[] {
  const byKey = new Map(existing.map((r) => [r.key, r]));
  for (const r of incoming) byKey.set(r.key, r);
  return [...byKey.values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.key.localeCompare(b.key));
}

export function formatDay(runs: LedgerRun[]): string {
  return runs.map((r) => JSON.stringify(r)).join("\n") + (runs.length > 0 ? "\n" : "");
}

/** Group runs by day file. */
export function byDay(runs: LedgerRun[]): Map<string, LedgerRun[]> {
  const out = new Map<string, LedgerRun[]>();
  for (const r of runs) out.set(dayOf(r), [...(out.get(dayOf(r)) ?? []), r]);
  return out;
}

// ── Report ────────────────────────────────────────────────────────────────

export function quantile(values: number[], q: number): number | null {
  if (values.length === 0) return null;
  const s = [...values].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.max(0, Math.ceil(q * s.length) - 1));
  return s[idx]!;
}

export interface SeriesStat {
  workflow: string;
  job: string;
  runs: number;
  p50: number | null;
  p90: number | null;
  totalSeconds: number;
  failures: number;
  /** p50 in the previous window of the same length, for the trend. */
  prevP50: number | null;
}

/**
 * Runner time counts every job that executed (success or failure): the runner was paid for both.
 * Speed (p50, p90, change points) counts only successful jobs: a skipped or cancelled job's 0 s, or a
 * job that failed after a few seconds, would make the median look faster than a real pass.
 */
function counts(conclusion: string | null): boolean {
  return conclusion === "success" || conclusion === "failure";
}
function isSpeed(conclusion: string | null): boolean {
  return conclusion === "success";
}

export function jobStats(runs: LedgerRun[], window: { from: string; to: string }, prev: { from: string; to: string }): SeriesStat[] {
  const inWin = (r: LedgerRun, w: { from: string; to: string }): boolean => r.createdAt >= w.from && r.createdAt < w.to;
  const series = new Map<string, { cur: number[]; ok: number[]; prev: number[]; failures: number }>();
  for (const r of runs) {
    for (const j of r.jobs) {
      if (j.seconds === null || !counts(j.conclusion)) continue;
      const k = `${r.workflow}\u0000${j.name}`;
      if (!series.has(k)) series.set(k, { cur: [], ok: [], prev: [], failures: 0 });
      const s = series.get(k)!;
      if (inWin(r, window)) {
        s.cur.push(j.seconds);
        if (isSpeed(j.conclusion)) s.ok.push(j.seconds);
        if (j.conclusion === "failure") s.failures += 1;
      } else if (inWin(r, prev) && isSpeed(j.conclusion)) s.prev.push(j.seconds);
    }
  }
  return [...series]
    .filter(([, s]) => s.cur.length > 0)
    .map(([k, s]) => {
      const [workflow, job] = k.split("\u0000") as [string, string];
      return {
        workflow,
        job,
        runs: s.cur.length,
        p50: quantile(s.ok, 0.5),
        p90: quantile(s.ok, 0.9),
        totalSeconds: s.cur.reduce((a, b) => a + b, 0),
        failures: s.failures,
        prevP50: quantile(s.prev, 0.5),
      };
    })
    .sort((a, b) => b.totalSeconds - a.totalSeconds);
}

export interface StepStat {
  workflow: string;
  job: string;
  step: string;
  runs: number;
  p50: number | null;
  totalSeconds: number;
}

export function stepStats(runs: LedgerRun[], window: { from: string; to: string }): StepStat[] {
  const m = new Map<string, { all: number[]; ok: number[] }>();
  for (const r of runs) {
    if (r.createdAt < window.from || r.createdAt >= window.to) continue;
    for (const j of r.jobs) {
      if (!counts(j.conclusion)) continue;
      for (const s of j.steps) {
        const k = `${r.workflow}\u0000${j.name}\u0000${s.name}`;
        if (!m.has(k)) m.set(k, { all: [], ok: [] });
        m.get(k)!.all.push(s.seconds);
        if (isSpeed(s.conclusion)) m.get(k)!.ok.push(s.seconds);
      }
    }
  }
  return [...m]
    .map(([k, v]) => {
      const [workflow, job, step] = k.split("\u0000") as [string, string, string];
      return { workflow, job, step, runs: v.all.length, p50: quantile(v.ok, 0.5), totalSeconds: v.all.reduce((a, b) => a + b, 0) };
    })
    .sort((a, b) => b.totalSeconds - a.totalSeconds);
}

export interface ChangePoint {
  workflow: string;
  job: string;
  /** The first run after the change: its commit is where to start reading. */
  sha: string;
  title: string;
  createdAt: string;
  before: number;
  after: number;
  /** after / before − 1 */
  change: number;
}

/**
 * Where did a job get slower or faster? For each job, on runs of the default
 * branch (push and schedule: the same code path every time, no PR noise),
 * compare the median of the K runs before each point with the K runs from it.
 * Report the largest shift per job when it is at least `minRatio` and
 * `minSeconds` — the commit of the first run after it is the suspect.
 */
export function changePoints(
  runs: LedgerRun[],
  opts: { branch: string; k?: number; minRatio?: number; minSeconds?: number },
): ChangePoint[] {
  const k = opts.k ?? 5;
  const minRatio = opts.minRatio ?? 0.25;
  const minSeconds = opts.minSeconds ?? 60;
  const series = new Map<string, { r: LedgerRun; s: number }[]>();
  for (const r of runs) {
    if (r.branch !== opts.branch || (r.event !== "push" && r.event !== "schedule")) continue;
    for (const j of r.jobs) {
      if (j.seconds === null || !isSpeed(j.conclusion)) continue;
      const key = `${r.workflow}\u0000${j.name}`;
      series.set(key, [...(series.get(key) ?? []), { r, s: j.seconds }]);
    }
  }
  const out: ChangePoint[] = [];
  for (const [key, pts] of series) {
    pts.sort((a, b) => a.r.createdAt.localeCompare(b.r.createdAt));
    let best: ChangePoint | null = null;
    for (let i = k; i + k <= pts.length; i++) {
      const before = quantile(pts.slice(i - k, i).map((p) => p.s), 0.5)!;
      const after = quantile(pts.slice(i, i + k).map((p) => p.s), 0.5)!;
      if (before <= 0) continue;
      const change = after / before - 1;
      if (Math.abs(change) < minRatio || Math.abs(after - before) < minSeconds) continue;
      if (!best || Math.abs(change) > Math.abs(best.change)) {
        const [workflow, job] = key.split("\u0000") as [string, string];
        const first = pts[i]!.r;
        best = { workflow, job, sha: first.sha, title: first.title, createdAt: first.createdAt, before, after, change };
      }
    }
    if (best) out.push(best);
  }
  return out.sort((a, b) => Math.abs(b.after - b.before) - Math.abs(a.after - a.before));
}

export interface Cohort {
  workflow: string;
  /** The job that ran longest in these runs (by that job's median over the window). */
  longestJob: string;
  runs: number;
  wallP50: number | null;
  wallP90: number | null;
  /** This group's share of the workflow's total wall time over passed runs. */
  share: number;
}

/**
 * Runs that ran different jobs (a path filter, an `if:`, a docs-only push) wait different times, and
 * one median over the mix describes none of them. Group each workflow's passed runs by the longest
 * job each one ran, so every median covers runs that did comparable work.
 */
export function cohorts(runs: LedgerRun[], window: { from: string; to: string }): Cohort[] {
  const inWin = runs.filter((r) => r.createdAt >= window.from && r.createdAt < window.to && r.conclusion === "success" && r.wallSeconds !== null);
  const byWorkflow = new Map<string, LedgerRun[]>();
  for (const r of inWin) byWorkflow.set(r.workflow, [...(byWorkflow.get(r.workflow) ?? []), r]);
  const out: Cohort[] = [];
  for (const [workflow, rs] of byWorkflow) {
    const perJob = new Map<string, number[]>();
    for (const r of rs) for (const j of r.jobs) if (j.seconds !== null && isSpeed(j.conclusion)) perJob.set(j.name, [...(perJob.get(j.name) ?? []), j.seconds]);
    const median = new Map([...perJob].map(([name, secs]) => [name, quantile(secs, 0.5)!]));
    const groups = new Map<string, LedgerRun[]>();
    for (const r of rs) {
      let best: string | null = null;
      for (const j of r.jobs) {
        if (j.seconds === null || !isSpeed(j.conclusion)) continue;
        if (best === null || median.get(j.name)! > median.get(best)! || (median.get(j.name)! === median.get(best)! && j.name < best)) best = j.name;
      }
      const key = best ?? "(no job ran)";
      groups.set(key, [...(groups.get(key) ?? []), r]);
    }
    const total = rs.reduce((a, r) => a + r.wallSeconds!, 0);
    for (const [longestJob, g] of groups) {
      const walls = g.map((r) => r.wallSeconds!);
      out.push({ workflow, longestJob, runs: g.length, wallP50: quantile(walls, 0.5), wallP90: quantile(walls, 0.9), share: total > 0 ? walls.reduce((a, b) => a + b, 0) / total : 0 });
    }
  }
  return out.sort((a, b) => a.workflow.localeCompare(b.workflow) || b.share - a.share);
}

function mins(s: number | null): string {
  return s === null ? "—" : (s / 60).toFixed(1);
}

function pctChange(cur: number | null, prev: number | null): string {
  if (cur === null || prev === null || prev === 0) return "—";
  const c = (cur / prev - 1) * 100;
  return `${c > 0 ? "+" : ""}${c.toFixed(0)}%`;
}

function table(head: string[], rows: (string | number)[][]): string {
  const line = (cells: (string | number)[]): string => `| ${cells.map((c) => String(c).replace(/\|/g, "/")).join(" | ")} |`;
  return [line(head), line(head.map(() => "---")), ...rows.map(line)].join("\n");
}

export function renderReport(
  runs: LedgerRun[],
  opts: { days: number; now: Date; branch: string; top?: number; source?: string },
): string {
  const top = opts.top ?? 15;
  const to = opts.now.toISOString();
  const from = new Date(opts.now.getTime() - opts.days * 86_400_000).toISOString();
  const prevFrom = new Date(opts.now.getTime() - 2 * opts.days * 86_400_000).toISOString();
  const win = { from, to };
  const cur = runs.filter((r) => r.createdAt >= from && r.createdAt < to);
  const out: string[] = [];
  out.push(`# CI report — last ${opts.days} days to ${to.slice(0, 10)}`, "");
  out.push(
    `From \`${opts.source ?? "the ledger"}\` (${cur.length} runs in the window, ${runs.length} loaded). Times are runner time from the GitHub API. Total minutes count passed and failed jobs; medians count passed jobs only; skipped and cancelled jobs are left out. Runs still going when the ledger was pulled are not in it yet, and fast runs finish first, so the newest hours lean fast: pull again later before trusting them.`,
    "",
  );

  const byWorkflow = new Map<string, LedgerRun[]>();
  for (const r of cur) byWorkflow.set(r.workflow, [...(byWorkflow.get(r.workflow) ?? []), r]);
  out.push("## Workflows", "");
  out.push(
    table(
      ["workflow", "runs", "runner min (total)", "wall p50 min", "wall p90 min", "queue p50 min", "failed"],
      [...byWorkflow]
        .map(([w, rs]) => ({ w, rs, total: rs.reduce((a, r) => a + r.jobSeconds, 0) }))
        .sort((a, b) => b.total - a.total)
        .map(({ w, rs, total }) => [
          w,
          rs.length,
          mins(total),
          mins(quantile(rs.map((r) => r.wallSeconds).filter((x): x is number => x !== null), 0.5)),
          mins(quantile(rs.map((r) => r.wallSeconds).filter((x): x is number => x !== null), 0.9)),
          mins(quantile(rs.map((r) => r.queueSeconds).filter((x): x is number => x !== null), 0.5)),
          rs.filter((r) => r.conclusion === "failure").length,
        ]),
    ),
    "",
  );

  const groups = cohorts(runs, win);
  out.push(
    "## Wall time by kind of run",
    "",
    "The workflow table above is a blend. Here each group is the passed runs whose longest job was the same, so a docs-only push and a full run do not share one median. Read the group with the largest share as the wait that matters; never quote the blend as the wait.",
    "",
  );
  out.push(
    table(
      ["workflow", "longest job", "runs", "wall p50 min", "wall p90 min", "share of wall"],
      groups.slice(0, top * 2).map((g) => [g.workflow, g.longestJob, g.runs, mins(g.wallP50), mins(g.wallP90), `${(g.share * 100).toFixed(0)}%`]),
    ),
    "",
  );

  const jobs = jobStats(runs, win, { from: prevFrom, to: from });
  out.push(`## Jobs by total runner time (top ${top})`, "", "The trend column compares this window's median with the window before it.", "");
  out.push(
    table(
      ["workflow", "job", "runs", "total min", "p50 min", "p90 min", "trend (p50)", "failed"],
      jobs.slice(0, top).map((j) => [j.workflow, j.job, j.runs, mins(j.totalSeconds), mins(j.p50), mins(j.p90), pctChange(j.p50, j.prevP50), j.failures]),
    ),
    "",
  );

  const steps = stepStats(runs, win);
  out.push(`## Slowest steps (top ${top}, steps of ${STEP_FLOOR_SECONDS}s or more)`, "");
  out.push(
    table(
      ["workflow", "job", "step", "runs", "total min", "p50 min"],
      steps.slice(0, top).map((s) => [s.workflow, s.job, s.step, s.runs, mins(s.totalSeconds), mins(s.p50)]),
    ),
    "",
  );

  const cps = changePoints(runs, { branch: opts.branch });
  out.push(`## Where a job changed speed (\`${opts.branch}\` push and schedule runs)`, "");
  if (cps.length === 0) out.push("No job moved by 25% and 60 s between two five-run windows.", "");
  else {
    out.push(
      table(
        ["workflow", "job", "first run after", "commit", "before p50 min", "after p50 min", "change"],
        cps.slice(0, top).map((c) => [c.workflow, c.job, c.createdAt.slice(0, 16), `\`${c.sha.slice(0, 9)}\` ${c.title}`, mins(c.before), mins(c.after), pctChange(c.after, c.before)]),
      ),
      "",
    );
  }
  return out.join("\n");
}
